#!/usr/bin/perl
use utf8;
use lib qw();
use vars qw($B $C);
use List::Util qw(first max maxstr min minstr reduce shuffle sum);
use Encode qw(encode decode);
use DBI;
use Cache::Memcached::libmemcached;
use Config::Tiny;
use BlackCurtain::Ignorance;
use Net::Twitter;
#use Net::Twitter::Lite;

INIT
{
	$C = Config::Tiny->read_string(<<'EOF');
CACHE_DIR=/home/twihome2/cgi-bin/cache
CACHE_PREFIX=log
CACHE_EXPIRE=3600
TEMPLATE=/home/twihome2/cgi-bin

[Twitter]
CONSUMER_KEY=6LRZYrSsqXyhArpkI4Bw
CONSUMER_SECRET=UK2h78WjOxId8ICchBzoLIh0cgPghFb4wrorSm3k
ACCESS_TOKEN=132426553-czlqqmICDOEfKEjpdMfsjcqOFxMnQsbjsxUoCctR
ACCESS_TOKEN_SECRET=4RhnKsWqqlYV1U0vOWzjg2Se0CFpbLMKt8NCWnMtik

[MySQL]
HOST=127.0.0.1
PORT=3306
DATABASE=twihome_test
USERNAME=ga
PASSWORD=CTfVBJQpQjB7AMb8

INDEX_0=INSERT INTO `Token` (`id`,`screen_name`,`ACCESS_TOKEN`,`ACCESS_TOKEN_SECRET`) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE `ctime` = CURRENT_TIMESTAMP
INDEX_1=SELECT COUNT(*) FROM `Queue` WHERE `screen_name` = ? AND `order` LIKE ? AND `flag` & 1
INDEX_2=INSERT INTO `Queue` (`screen_name`,`order`) VALUES(?,?)
SHOW_0=SELECT * FROM `Queue` WHERE `screen_name` = ? ORDER BY `ctime` DESC LIMIT 0,40
SALVAGE_0=SELECT ?,`id` FROM `Tweet` WHERE `screen_name` = ? AND `flag` & ? ORDER BY `created_at` ASC LIMIT 0,1
SALVAGE_1=SELECT ?,`id` FROM `Tweet` WHERE `screen_name` = ? AND `flag` & ? ORDER BY `created_at` DESC LIMIT 0,1

[Memcached]
HOST=127.0.0.1:11211

[QueueDescription]
SALVAGE.TIMELINE=過去のツイート取得 (200件)
SALVAGE.MENTION=過去のリプライ取得 (200件)
SALVAGE.FAVORITE=過去のお気に入り取得 (200件)

EOF
	$B = {
		DBI =>DBI->connect(sprintf("dbi:mysql:database=%s;host=%s;port=%d",@{$C->{MySQL}}{qw(DATABASE HOST PORT)}),@{$C->{MySQL}}{qw(USERNAME PASSWORD)}),
		Cache::Memcached =>Cache::Memcached::libmemcached->new({servers =>[split(/ /o,$C->{Memcached}->{HOST})]}),
	};
	for(grep(/_[0-9]$/,keys(%{$C->{MySQL}}))){
		$B->{"STH_".$_} = $B->{DBI}->prepare($C->{MySQL}->{$_});
	}
}

BlackCurtain::Ignorance->new(
	[
		[qr/./,\&cb_prepare],
		[qr/^\/?$/,\&cb_index],
		[qr/^\/(\w+)(?:\.([a-z]+))?(?:\/[fjr])?\/?$/,\&cb_show],
	],
	CGI::Session =>["driver:memcached",undef,{Memcached =>$B->{Cache::Memcached}}],
	Text::Xslate =>[path =>[split(/ /o,$C->{_}->{TEMPLATE})],cache_dir =>$C->{_}->{CACHE_DIR}],
)->perform();

exit(0);

sub cb_prepare
{
	if($SES{ACCESS_TOKEN} && $SES{ACCESS_TOKEN_SECRET}){
		$B->{Net::Twitter} = Net::Twitter->new(
			traits =>[qw(API::REST API::Search OAuth WrapError RetryOnError)],
			consumer_key =>$C->{Twitter}->{CONSUMER_KEY},
			consumer_secret =>$C->{Twitter}->{CONSUMER_SECRET},
			access_token =>$SES{ACCESS_TOKEN},
			access_token_secret =>$SES{ACCESS_TOKEN_SECRET},
			max_retries =>2,
		);
	}
	if(!$B->{Net::Twitter}){
		$B->{Net::Twitter} = Net::Twitter->new(
			traits =>[qw(API::REST API::Search OAuth WrapError RetryOnError)],
			consumer_key =>$C->{Twitter}->{CONSUMER_KEY},
			consumer_secret =>$C->{Twitter}->{CONSUMER_SECRET},
			access_token =>$C->{Twitter}->{ACCESS_TOKEN},
			access_token_secret =>$C->{Twitter}->{ACCESS_TOKEN_SECRET},
			max_retries =>2,
		);
	}
	return();
}

sub cb_index
{
	if(!defined($GET{op})){
		return("Text::Xslate",{},data =><<'EOF');
<html>
<head>
<title>ろぐをとるだけ</title>
<body>
<p><a href="/?op=login">a</a></p>
</body>
</html>
EOF
	}elsif($GET{op} eq "login" && $GET{oauth_token} && $GET{oauth_verifier}){
		$B->{Net::Twitter}->request_token($SES{REQUEST_TOKEN});
		$B->{Net::Twitter}->request_token_secret($SES{REQUEST_TOKEN_SECRET});
		@SES{qw(ACCESS_TOKEN ACCESS_TOKEN_SECRET id screen_name)} = $B->{Net::Twitter}->request_access_token(token =>$GET{oauth_token},verifier =>$GET{oauth_verifier});
		if($SES{id} > 0){
			sub set_queue
			{
				if(!$B->{STH_INDEX_1}->execute(@_)){
					warn(sprintf("%s() : %s",(caller(0))[3]),"");
					return();
				}elsif(($B->{STH_INDEX_1}->fetchrow_array())[0] == 0 && $B->{STH_INDEX_2}->execute(@_) == 0){
					warn(sprintf("%s() : %s",(caller(0))[3]),"");
					return();
				}
				return(1);
			}
			if($B->{STH_INDEX_0}->execute(@SES{qw(id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)}) == 0){
				return(&cb_exception(undef,undef,undef,"認証失敗"));
			}elsif(!&set_queue($SES{screen_name},"SALVAGE.TIMELINE")){
				return(&cb_exception(undef,undef,undef,"認証失敗"));
			}elsif(!&set_queue($SES{screen_name},"SALVAGE.MENTION")){
				return(&cb_exception(undef,undef,undef,"認証失敗"));
			}elsif(!&set_queue($SES{screen_name},"SALVAGE.FAVORITE")){
				return(&cb_exception(undef,undef,undef,"認証失敗"));
			}
			return("jump","http://".$ENV{HTTP_HOST}.$ENV{SCRIPT_NAME}."/".$SES{screen_name});
		}else{
			return(&cb_exception(undef,undef,undef,"認証失敗"));
		}
	}elsif($GET{op} eq "login"){
		my $r = $B->{Net::Twitter}->get_authorization_url(callback =>"http://".$ENV{HTTP_HOST}.$ENV{SCRIPT_NAME}."/?op=login");
		$SES{REQUEST_TOKEN} = $B->{Net::Twitter}->request_token();
		$SES{REQUEST_TOKEN_SECRET} = $B->{Net::Twitter}->request_token_secret();

		return("jump",$r);
	}elsif($GET{op} eq "logout"){
	}else{
	}
	return("raw","unknown op");
}

sub cb_show
{
	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name,$page) = @{$q};
	my($screen_name,$issue) = @{$m};

	my $r;
	my $sign = join(".",$C->{_}->{CACHE_PREFIX},$screen_name).".";
	if(!defined($r = $B->{Cache::Memcached}->get($sign."profile"))){
		if(!($r = $B->{Net::Twitter}->show_user({screen_name =>$screen_name}))){
			return(&cb_exception(undef,undef,undef,"ユーザ情報取得失敗"));
		}
		$B->{Cache::Memcached}->set($sign."profile",$r,$C->{_}->{CACHE_EXPIRE});
	}

	if(!defined($page)){
		if(!defined($r->{status} = $B->{Cache::Memcached}->get($sign."timeline"))){
			if(!($r->{status} = &salvage(undef,$m,undef,[2,1]))){
				return(&cb_exception(undef,undef,undef,"ユーザ情報取得失敗"));
			}
			$B->{Cache::Memcached}->set($sign."timeline",$r->{status},$C->{_}->{CACHE_EXPIRE});
		}
	}elsif($page eq "j"){
		if($B->{STH_SHOW_0}->execute($r->{screen_name})){
			map{$_->{description} = $C->{QueueDescription}->{uc($_->{order})}}@{$r->{_queue} = $B->{STH_SHOW_0}->fetchall_arrayref({})};
		}
	}

	return($issue ? $issue : "Text::Xslate",$r,data =><<'EOF');
<html>
<head>
<title>ろぐとるだけったー</title>
<style type="text/css">
body
{
	color: #<:$profile_text_color:>;
	background-color: #<:$profile_background_color:>;
	font-size: 10pt;
}

th,td
{
	border-right: solid 1px #<:$profile_sidebar_border_color:>;
	border-bottom: solid 1px #<:$profile_sidebar_border_color:>;
	text-align: center;
	font-size: 10pt;
}

.line
{
	border: solid 1px #000000;
}
.pile
{
	float: left;
}

.overall
{
	margin: 4px auto 0px auto;
	width: 674px; # 640 + 16(menu margin) + 16(menu padding) + 2(menu border)
}
.menu
{
	background-color: #<:$profile_sidebar_fill_color:>;
	margin: 0px 0px 0px 16px;
	padding: 8px 16px 8px 0px;
	border: solid 1px #<:$profile_sidebar_border_color:>;
	width: 160px;
}
.main
{
	width: 480px;
}

.tab
{
	margin: 0px 0px -1px -1px;
	padding: 8px 0px 8px 0px;
	border: solid 1px #<:$profile_sidebar_border_color:>;
	text-align: center;
}
.tab_active
{
	background-color: #<:$profile_background_color:>;
	border-left: solid 1px #<:$profile_background_color:>;
}
</style>
</head>
<body>
<div class="overall">
	<div class="main pile">
		<div class="">
			<table style="width: 100%;">
				<tr>
					<th></th>
					<th>登録時</th>
					<th>優先度</th>
					<th>内容</th>
					<th>状態</th>
				</tr>
: for $_queue -> $queue {
				<tr>
					<td style="width: 24px;"><:$queue.id:></td>
					<td style="width: 128px;"><:$queue.ctime:></td>
					<td style="width: 48px;"><:$queue.priority:></td>
					<td style="text-align: left;"><:$queue.description:></td>
					<td style="width: 48px;"><:$queue.flag:></td>
				</tr>
: }
			</table>
		</div>
	</div>
	<div class="menu pile">
		<div class=""><span id="name"><:$name:></span></div>
		<div class="">&nbsp;#<span id="id"><:$id:></span></div>
		<div class="">&nbsp;@<span id="screen_name"><:$screen_name:></span></div>
		<div class="tab tab_active"><a href="<:$screen_name:>">ついっと</a></div>
		<div class="tab"><a href="<:$screen_name:>/r">@<:$screen_name:></a></div>
		<div class="tab"><a href="<:$screen_name:>/f"><span style="color: yellow;">★</span></a></div>
		<div class="tab"><a href="<:$screen_name:>/j">きゅー</a></div>
	</div>
</div>
</body>
</html>
EOF
}

sub salvage
{
	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name) = @{$q};
	my($screen_name,$issue) = @{$m};
	my($flag,$axis) = @{$g};

	my $r;
	if($flag & 1){
	}elsif($flag & 2){
		my @g;
		if($axis){
			if(!$B->{STH_SALVAGE_0}->execute("since_id",$screen_name,$flag)){
			}
			@g = $B->{STH_SALVAGE_0}->fetchrow_array();
		}else{
			if(!$B->{STH_SALVAGE_1}->execute("max_id",$screen_name,$flag)){
			}
			@g = $B->{STH_SALVAGE_1}->fetchrow_array();
		}

		if(!($r = $B->{Net::Twitter}->user_timeline({screen_name =>$screen_name,@g,count =>200,include_entities =>1,include_rts =>1}))){
			return();
		}
	}elsif($flag & 4){
	}
	return([@{$r}[0..39]]);
}

__DATA__


#!/usr/bin/perl
use constant CACHE_EXPIRE =>3600;
use lib qw(/home/twihome2/cgi-bin);
use vars qw($B %h);
use utf8;
use List::Util qw(sum min max);
use Encode qw(encode decode);
use DBI;
use Storable qw(nfreeze thaw);
#use Cache::File;
use Cache::FileCache;
#use Cache::Memory;
use DateTime;
use DateTime::Locale;
use DateTime::Format::DateParse;
use DateTime::Format::MySQL;
use LWP::Simple;
use URI::Escape;
use XML::Simple;
use JSON qw(encode_json decode_json);
#use Net::Twitter::Lite;
#use Text::ChaSen;
#use Text::MeCab;
use MeCab;
use URI::GoogleChart;
use Data::Dumper;


sub get_user_twitter_status_common
{
	use constant F_TWEET =>1 << 0;
	use constant F_REPLYFROM =>1 << 1;
	use constant F_REPLYTO =>1 << 2;
	use constant F_RETWEETFROM =>1 << 3;
	use constant F_RETWEETTO =>1 << 4;
	use constant F_FAVORITEFROM =>1 << 5;
	use constant F_FAVORITETO =>1 << 6;
	use constant F_TWEETWITHHASH =>1 << 7;

	#warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : ");
	my $cap = shift();
	my $screen_name = shift();
	my %a = @_;

	sub rep_link
	{
		my $p = shift();
		my $k = shift();
		my $d = shift() || [];
		my $prefix = shift() || [];
		my $suffix = shift() || [];
		$p->{$k."_raw"} = $p->{$k};
		$p->{$k} =~s/(https?:\/{2}[^\x00-\x20\x7F]+)/<a href="$1" target="_blank">$1<\/a>/go;
		$p->{$k} =~s/\@([0-9A-Za-z_]+)/<a href="$d->[1]\/$1"><span class="link-point">\@<\/span>$prefix->[1]$1$suffix->[1]<\/a>/go;
		$p->{$k} =~s/#([^\x00-\x20\x7F]+)/<a href="$d->[2]\/$1"><span class="link-point">#<\/span>$prefix->[2]$1$suffix->[2]<\/a>/go;
		return();
	}
	sub set_created_at
	{
		my $p = shift();
		my $k = shift();
		my $DateTime = DateTime::Format::DateParse->parse_datetime($p->{$k});
		$DateTime->set_locale(DateTime::Locale->load("ja_JP"));
		$DateTime->set_time_zone("Asia/Tokyo");
		$p->{$k."_ymd"} = $DateTime->ymd("-");
		$p->{$k."_hms"} = $DateTime->hms(":");
		$p->{$k."_d"} = $DateTime->day();
		$p->{$k."_ymdwJP"} = $DateTime->strftime("%Y年%m月%d日(%a)");
		$p->{$k."_MySQL"} = DateTime::Format::MySQL->format_datetime($DateTime);
		return();
	}

	my $r = [];
	if($cap == F_TWEET){
		my $since_id = $B->{DBI}->selectrow_array("SELECT `id` FROM `tweet` WHERE `screen_name` = ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,1",{},$screen_name,F_TWEET);
		if(!($r = $B->{Net::Twitter}->user_timeline({screen_name =>$screen_name,count =>200,$since_id > 0 ? (since_id =>$since_id) : (),include_rts =>1,include_entities =>1}))){
			warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : ".$B->{Net::Twitter}->get_error());
			return();
		}
	}elsif($cap == F_REPLYFROM){
		my $since_id = $B->{DBI}->selectrow_array("SELECT `id` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_reply`) AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,1",{},$screen_name,F_REPLYFROM);
		#if(!($r = $B->{Net::Twitter}->mentions({screen_name =>$screen_name,count =>200,$since_id > 0 ? (since_id =>$since_id) : (),include_rts =>1,include_entities =>1}))){
		if(!($r = $B->{Net::Twitter}->search({q =>"\@".$screen_name,count =>200,$since_id > 0 ? (since_id =>$since_id) : (),include_rts =>1,include_entities =>1})->{results})){
			warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : ".$B->{Net::Twitter}->get_error());
			return();
		}
		map{$_->{user}->{screen_name} = $_->{from_user}}@{$r};
	}elsif($cap == F_FAVORITETO){
		my $since_id = $B->{DBI}->selectrow_array("SELECT `id` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_favorite`) AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,1",{},$screen_name,F_FAVORITETO);
		if(!($r = $B->{Net::Twitter}->favorites({screen_name =>$screen_name,count =>200,$since_id > 0 ? (since_id =>$since_id) : (),include_rts =>1,include_entities =>1}))){
			warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : ".$B->{Net::Twitter}->get_error());
			return();
		}
	}

	map{
		&rep_link($_,"text",[undef,undef,"/-hash"]);
		&set_created_at($_,"created_at");
		my $tweet_reply = join(",",$_->{text_raw} =~m/\@([0-9A-Za-z_]+)/go);
		my $tweet_favorite = F_FAVORITETO ? $screen_name : undef;
		my $tweet_hashtag = join(",",$_->{text_raw} =~m/#([^\x00-\x20\x7F]+)/go);
		my $tweet_cap = $cap;
		if($tweet_reply){
			$tweet_cap |= F_REPLYTO;
		}
		if($tweet_hashtag){
			$tweet_cap |= F_TWEETWITHHASH;
		}
		$B->{DBI}->do(
			"INSERT INTO `tweet` (`screen_name`,`id`,`created_at`,`text`,`struct`,`tweet_reply`,`tweet_favorite`,`tweet_hashtag`,`tweet_cap`) VALUES(?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `tweet_cap` = `tweet_cap` | ?,`tweet_favorite` = IF(FIND_IN_SET(?,`tweet_favorite`),`tweet_favorite`,CONCAT_WS(',',`tweet_favorite`,?))",
			{},
			$_->{user}->{screen_name},
			$_->{id},
			$_->{created_at_MySQL},
			$_->{text_raw},
			nfreeze($_),
			$tweet_reply,
			$tweet_favorite,
			$tweet_hashtag,
			$tweet_cap,
			F_TWEET,
			$_->{user}->{screen_name},
			$tweet_favorite,
		);
	}@{$r};
	warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : db push ".($#{$r} + 1)." record.");

	return(1);
}

sub cb_user_twitter_timeline
{
	my $q = shift();
	my($screen_name,undef,$args) = @{$q};
	my $sign = join("/",CACHE_PREFIX,$screen_name,(caller(0))[3]);

	my $r;
	if(!defined($r = $B->{Cache::FileCache}->get($sign))){
		warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : read source.");
		if(&get_user_twitter_status_common(F_TWEET,$screen_name,{read =>"update"}) && ($r = (&cb_user_twitter_timeline_log($q))[1])){
			$B->{Cache::FileCache}->set($sign,$r);
		}
	}
	return("Dumper",$r);
}

sub cb_user_twitter_timeline_log
{
	my $q = shift();
	shift();
	shift();
	shift();
	my $tweet_cap = shift() || F_TWEET;
	my($screen_name,undef,$args) = @{$q};
	my $sign = join("/",CACHE_PREFIX,$screen_name,(caller(0))[3]);

	my $r;
	if($args =~ /^([0-9]+)\-$/o){
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE `screen_name` = ? AND `id` > ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$1,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}elsif($args =~ /^\-([0-9]+)$/o){
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE `screen_name` = ? AND `id` < ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$1,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}else{
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE `screen_name` = ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}
	return("Dumper",$r);
}

sub cb_user_twitter_replies
{
	my $q = shift();
	my($screen_name,undef,$args) = @{$q};
	my $sign = join("/",CACHE_PREFIX,$screen_name,(caller(0))[3]);

	my $r;
	#if(!defined($r = $B->{Cache::FileCache}->get($sign))){
		warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : read source.");
		if(&get_user_twitter_status_common(F_REPLYFROM,$screen_name,{read =>"update"}) && ($r = (&cb_user_twitter_replies_log($q,undef,undef,undef,F_REPLYFROM))[1])){
			$B->{Cache::FileCache}->set($sign,$r);
		}
	#}
	return("Dumper",$r);
}

sub cb_user_twitter_replies_log
{
	my $q = shift();
	shift();
	shift();
	shift();
	my $tweet_cap = shift() || F_REPLYFROM;
	my($screen_name,undef,$args) = @{$q};
	my $sign = join("/",CACHE_PREFIX,$screen_name,(caller(0))[3]);

	my $r;
	if($args =~ /^([0-9]+)\-$/o){
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_reply`) AND `id` > ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$1,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}elsif($args =~ /^\-([0-9]+)$/o){
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_reply`) AND `id` < ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$1,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}else{
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_reply`) AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}
	return("Dumper",$r);
}

sub cb_user_twitter_favorites
{
	my $q = shift();
	my($screen_name,undef,$args) = @{$q};
	my $sign = join("/",CACHE_PREFIX,$screen_name,(caller(0))[3]);

	my $r;
	#if(!defined($r = $B->{Cache::FileCache}->get($sign))){
		warn("TwihomeCore \&".(caller(0))[3]."(".join(",",@_).") : read source.");
		if(&get_user_twitter_status_common(F_FAVORITETO,$screen_name,{read =>"update"}) && ($r = (&cb_user_twitter_favorites_log($q))[1])){
			# Dumping circular structures is not supported with JSON::Syck
			my $fixsub = sub{
				my $p = shift();
				while(my($k,$v) = each(%{$p})){
					if(ref($p->{$k}) eq "JSON::XS::Boolean"){
						$p->{$k} = undef;
					}
				}
				return();
			};
			map{
				&{$fixsub}($_);
				&{$fixsub}($_->{user});
			}@{$r};
			$B->{Cache::FileCache}->set($sign,$r);
		}
	#}
	return("Dumper",$r);
}

sub cb_user_twitter_favorites_log
{
	my $q = shift();
	shift();
	shift();
	shift();
	my $tweet_cap = shift() || F_FAVORITETO;
	my($screen_name,undef,$args) = @{$q};
	my $sign = join("/",CACHE_PREFIX,$screen_name,(caller(0))[3]);

	my $r;
	if($args =~ /^([0-9]+)\-$/o){
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_favorite`) AND `id` > ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$1,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}elsif($args =~ /^\-([0-9]+)$/o){
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_favorite`) AND `id` < ? AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$1,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}else{
		if($r = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE FIND_IN_SET(?,`tweet_favorite`) AND `tweet_cap` & ? ORDER BY `created_at` DESC LIMIT 0,20",{},$screen_name,$tweet_cap)){
			$r = [map{thaw($_->[0])}@{$r}];
		}
	}
	return("Dumper",$r);
}

sub cb_user_twitter_timeline_analysis
{
	my $st = (&cb_user_twitter_profile(@_))[1];

	my $r;
	if($st){
		$r = {map{$_,$st->{$_}}grep(/^tweet_analyze_.+?_url$/o,keys(%{$st}))};
	}
	return("JSON",$r);
}

sub cb_user_twitter_timeline_search
{
	warn("search word: ".join(",",@{$_[0]}));
	my $a = shift();

	my $r;
	if(my $result = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE `screen_name` = ? AND `text` LIKE ? ORDER BY `created_at` DESC",{},$a->[0],"%".$a->[2]."%")){
		$r = [map{thaw($_->[0])}@{$result}];
	}
	return("JSON",$r);
}

sub cb_user_twitter_timeline_date
{
	my $a = shift();

	my $r;
	if(my $result = $B->{DBI}->selectall_arrayref("SELECT `struct` FROM `tweet` WHERE `screen_name` = ? AND DATE(`created_at`) = ? ORDER BY `created_at` DESC",{},$a->[0],$a->[2])){
		$r = [map{thaw($_->[0])}@{$result}];
	}
	return("JSON",$r);
}

sub cb_user_twitter_keyword
{
	my @w = map{$_->{text_raw}}@{(&cb_user_twitter_timeline(@_))[1]};

	# perl say: Can't use "my $a" in sort comparison
	my $a_ = shift();

	my $sig = join("/",CACHE_PREFIX,$a_->[0],"user_keyword");
	my $r = {};
	if(!defined($r = $B->{Cache::FileCache}->get($sig))){
		map{
			s/https?:\/{2}[\x21-\x7E]+//igo;
			s/RT \@[\w]+://igo;
			s/\@[\w]+//igo;
			s/\#[^\x20]+//igo;
		}@w;

		my %a = (engine =>"mecab");
		my %w;
		if(!defined($a{engine}) || $a{engine} eq "mecab"){
			foreach(@w){
				foreach(grep{(split(/\s+/o,$_))[1] =~ /名詞,一般/o}split(/\n/o,decode("utf8",$B->{MeCab}->parse($_)))){
					++$w{(split(/\s+/o,$_))[0]};
				}
			}
		}elsif($a{engine} eq "chasen"){
			foreach(@w){
				foreach(grep{(split(/\s+/o,$_))[3] =~ /名詞/o}split(/\n/o,Text::ChaSen::sparse_tostr($_))){
					++$w{(split(/\s+/o,$_))[2]};
				}
			}
		}else{
			die;
		}
		$r = [map{{word =>$_,size =>$w{$_} > 5 ? 1 : 6 - $w{$_}}}(sort{$w{$b}<=>$w{$a}}keys(%w))[0..9]];
		$B->{Cache::FileCache}->set($sig,$r);
		warn("Twihome2 core/".(caller(0))[3].": read source.\n");
	}
	return($GET{f} eq "yaml" ? "YAML" : "JSON",$r);
}

sub cb_user_youtube
{
	my @w = map{$_->{word}}@{(&cb_user_twitter_keyword(@_))[1]};
	my $a = shift();

	my $sig = join("/",CACHE_PREFIX,$a->[0],"youtube");
	my $r;
	if(!defined($r = $B->{Cache::FileCache}->get($sig))){
		$r = [values(%{&spider("http://gdata.youtube.com/feeds/api/videos/?vq=%s&max-results=%d",[join(" ",@w[0..2]),5])->{entry}})];
		$B->{Cache::FileCache}->set($sig,$r);
		warn("Twihome2 core/".(caller(0))[3].": read source. (".$sig.")\n");
	}
	return("JSON",$r);
}

sub cb_user_google_blog
{
	my @w = map{$_->{word}}@{(&cb_user_twitter_keyword(@_))[1]};
	my $a = shift();

	my $sig = join("/",CACHE_PREFIX,$a->[0],"google_blog");
	my $r;
	if(!defined($r = $B->{Cache::FileCache}->get($sig))){
		$r = &spider("http://ajax.googleapis.com/ajax/services/search/blogs?v=1.0&q=%s",[join(" ",@w[0..1]),5],type =>"json");
		$B->{Cache::FileCache}->set($sig,$r);
		warn("Twihome2 core/".(caller(0))[3].": read source.\n");
	}
	return("JSON",$r);
}

sub cb_user_find2ch
{
	my @w = map{$_->{word}}@{(&cb_user_twitter_keyword(@_))[1]};
	my $a = shift();

	my $sig = join("/",CACHE_PREFIX,$a->[0],"find2ch");
	my $r;
	if(!defined($r = $B->{Cache::FileCache}->get($sig))){
		# find2ch is bugged, need more tests.
		#$r = &spider("http://find.2ch.net/?STR=%s&COUNT=%d&TYPE=TITLE&BBS=ALL",[join(" ",@w[0]),5],type =>"html",regex =>qr/<dt><a href="(http:\/{2}[\w]+\.2ch\.net\/.+?)">([^<>]+)<\/a>/);
		$r = &spider("http://find.2ch.net/?STR=%s",[join(" ",@w[0..0]),5],type =>"html",regex =>qr/<dt><a href="(http:\/{2}[\w]+\.2ch\.net\/.+?)">([^<>]+)<\/a>/);
		$B->{Cache::FileCache}->set($sig,$r);
		warn("Twihome2 core/".(caller(0))[3].": read source.\n");
	}
	return("JSON",$r);
}

sub cb_user_hatena_diary
{
	my @w = map{$_->{word}}@{(&cb_user_twitter_keyword(@_))[1]};
	unshift(@w,"site:d.hatena.ne.jp");
	my $a = shift();

	my $sig = join("/",CACHE_PREFIX,$a->[0],"hatena");
	my $r;
	if(!defined($r = $B->{Cache::FileCache}->get($sig))){
		$r = &spider("http://ajax.googleapis.com/ajax/services/search/web?v=1.0&q=%s",[join(" ",@w[0..1]),5],type =>"json");
		$B->{Cache::FileCache}->set($sig,$r);
		warn("Twihome2 core/".(caller(0))[3].": read source.\n");
	}
	return("JSON",$r);
}

sub user
{
my $u = fetchTwitterUser("namusyaka");
my $t = fetchTwitterTimeline("namusyaka",20);
my $k = fetch(\&fetchKeyword,[[map{$_->{text}}@{$t}],engine =>"mecab"],cache =>"namusyaka"."_MeCab",type =>"raw");
my %a = (
	%{$u},
	timeline =>$t,
	keyword =>$k,
	youtube =>fetchYouTube(join(" ",@{$k}),5),
	#find2ch =>fetchFind2ch(join(" ",@{$k}),5),
	gblog =>fetchGoogleBlog(join(" ",@{$k})),
);
}

sub spider
{
	my $l = shift();
	my $a = shift();
	my %a = @_;

	my $r;
	#if(!defined($a{cache}) || !defined($r = $h{Cache::FileCache}->get(CACHE_PREFIX.$a{cache}))){
		warn("spider: ".sprintf($l,map{uri_escape_utf8($_)}@{$a}));
		if(ref($l) eq "CODE" && defined(&{$l}) && !defined($r = &{$l}(@{$a}))){
		}elsif($l =~ /^file:\/{2}(.+?)$/o){
		}elsif($l =~ /^https?:\/{2}/o & !defined($r = get(sprintf($l,map{uri_escape_utf8($_)}@{$a})))){
			die;
		}else{
		}

		if((!defined($a{type}) || $a{type} eq "xml") && !defined($r = XML::Simple->new()->XMLin($r))){
			die;
		}elsif($a{type} eq "json" && !defined($r = decode_json(encode("utf-8",$r)))){
			die;
		}elsif($a{type} eq "html" && !defined($r = do{my @r;while($r =~ /$a{regex}/ig){push(@r,[$1,$2,$3,$4,$5,$6,$7,$8,$9])}$#r != -1 ? \@r : undef})){
			#die;
		}elsif($a{type} eq "raw"){
		}else{
		}

		#if(defined($r)){
		#	$h{Cache::FileCache}->set(CACHE_PREFIX.$a{cache},$r);
		#}
	#}else{
	#}
	return(ref($r) ? $r : undef)
}



1;
