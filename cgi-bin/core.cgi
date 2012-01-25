#!/usr/bin/perl
use 5.10.1;
use utf8;
use lib qw(/usr/local/lib/perl);
use vars qw($B $C);
use List::Util qw(first max maxstr min minstr reduce shuffle sum);
use Encode qw(encode decode);
use Compress::Zlib;
use Storable qw(thaw nfreeze);
use DBI;
use Cache::Memcached::libmemcached;
use XML::Simple;
use Config::Tiny;
use BlackCurtain::Ignorance;
use DateTime;
use DateTime::Locale;
use DateTime::Format::DateParse;
use DateTime::Format::MySQL;
use Net::Twitter;
#use Net::Twitter::Lite;
use constant F_NULL =>0;
use constant F_QUEUE =>1 << 0;
use constant F_PROCESS =>1 << 1;
use constant F_FINISH =>1 << 2;
use constant F_FAILURE =>1 << 3;
use constant F_STATE =>F_QUEUE|F_PROCESS|F_FINISH|F_FAILURE;
use constant F_TMPORARY =>1 << 6;
use constant F_REGULAR =>1 << 7;
use constant F_TWEETS =>1 << 8;
use constant F_REPLIES =>1 << 9;
use constant F_RETWEETS =>1 << 10;
use constant F_QUOTETWEETS =>1 << 11;
use constant F_FAVORITES =>1 << 12;
use constant F_REPLYTO =>1 << 13;
use constant F_RETWEETED =>1 << 14;
use constant F_QUOTETWEETED =>1 << 15;
use constant F_API =>F_TWEETS|F_REPLIES|F_FAVORITES|F_RETWEETED;
use constant I_PRIORITY_LOW =>1;
use constant I_PRIORITY_MIDIUM =>2;
use constant I_PRIORITY_HIGH =>3;

INIT
{
	$C = Config::Tiny->read_string(<<'EOF');
TIMEZONE=Asia/Tokyo
LOCALE=ja_JP

CACHE_DIR=/tmp
CACHE_PREFIX=twittotter
CACHE_EXPIRE=3600
TEMPLATE=/var/www/twittotter/html

LIMIT=48

[Twitter]
CONSUMER_KEY=6LRZYrSsqXyhArpkI4Bw
CONSUMER_SECRET=UK2h78WjOxId8ICchBzoLIh0cgPghFb4wrorSm3k
ACCESS_TOKEN=132426553-czlqqmICDOEfKEjpdMfsjcqOFxMnQsbjsxUoCctR
ACCESS_TOKEN_SECRET=4RhnKsWqqlYV1U0vOWzjg2Se0CFpbLMKt8NCWnMtik

LOGGEDIN_HOME_TIMELINE_COUNT=200
LOGGEDIN_MENTIONS_COUNT=200
LOGGEDIN_FAVORITES_COUNT=200
LOGGEDIN_RETWEETED_BY_COUNT=200
DEFAULT_HOME_TIMELINE_COUNT=40
DEFAULT_MENTIONS_COUNT=0
DEFAULT_FAVORITES_COUNT=40
DEFAULT_RETWEETED_BY_COUNT=40

[MySQL]
HOST=localhost
PORT=3306
DATABASE=twittotter
USERNAME=root
PASSWORD=

INIT_0=SET NAMES 'utf8'
METHOD_0=SELECT `user_id` FROM `Token` WHERE `screen_name` = ? LIMIT 0,1
METHOD_1=SELECT `user_id` FROM `Queue` WHERE `screen_name` = ? LIMIT 0,1
METHOD_2=SELECT `user_id` FROM `Tweet` WHERE `screen_name` = ? LIMIT 0,1
METHOD_3=SELECT `screen_name` FROM `Token` WHERE `user_id` = ? LIMIT 0,1
METHOD_4=SELECT `screen_name` FROM `Queue` WHERE `user_id` = ? LIMIT 0,1
METHOD_5=SELECT `screen_name` FROM `Tweet` WHERE `user_id` = ? LIMIT 0,1
CLI_QC_0=TRUNCATE TABLE `Queue`
CLI_QI_0=SELECT * FROM `Queue` WHERE `user_id` = ? AND `order` LIKE ? AND `flag` & ? = ? LIMIT 0,1
CLI_QI_1=
CLI_QI_2=INSERT `Queue` (`user_id`,`screen_name`,`order`,`priority`,`flag`) VALUES(?,?,?,?,?)
CLI_QE_0=SELECT * FROM `Queue` LEFT JOIN `Token` ON `Queue`.`user_id` = `Token`.`user_id` WHERE `flag` & 1 ORDER BY `Queue`.`priority`,`Queue`.`ctime` LIMIT 0,1
CLI_QE_1=UPDATE `Queue` SET `flag` = ?,`mtime` = CURRENT_TIMESTAMP WHERE `id` = ?
SALVAGE_0=SELECT ?,`status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` DESC LIMIT 0,1
SALVAGE_1=SELECT ?,`status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` ASC LIMIT 0,1
SALVAGE_2=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_3=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
SALVAGE_4=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_5=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
SALVAGE_6=INSERT `Tweet` (`status_id`,`user_id`,`screen_name`,`text`,`created_at`,`structure`,`flag`) VALUES (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `structure` = VALUES(`structure`),`flag` = `flag` | ?
SALVAGE_7=SELECT 1 FROM `Bind` WHERE `status_id` = ? AND (`referring_user_id` = ? OR `referring_user_screen_name` = ?) AND (`referred_user_id` = ? OR `referred_user_screen_name` = ?) AND `flag` | ? = ?
SALVAGE_8=INSERT `Bind` (`status_id`,`referring_user_id`,`referring_user_screen_name`,`referred_user_id`,`referred_user_screen_name`,`flag`) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `flag` = `flag` | ?
SALVAGE_9=SELECT * FROM `Tweet` WHERE `status_id` = ? LIMIT 0,1

INDEX_0=INSERT `Token` (`id`,`screen_name`,`ACCESS_TOKEN`,`ACCESS_TOKEN_SECRET`) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE `ctime` = CURRENT_TIMESTAMP
SHOW_0=SELECT * FROM `Queue` WHERE `screen_name` = ? ORDER BY `ctime` DESC LIMIT 0,40

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
		$B->{"DBT_".$_} = $B->{DBI}->prepare($C->{MySQL}->{$_});
	}
	$B->{DBT_INIT_0}->execute();
}

sub user_id
{
	my($screen_name) = @_;

	if($B->{DBT_METHOD_0}->execute($screen_name) != 0){
		return($B->{DBT_METHOD_0}->fetch()->[0]);
	}elsif($B->{DBT_METHOD_1}->execute($screen_name) != 0){
		return($B->{DBT_METHOD_1}->fetch()->[0]);
	}elsif($B->{DBT_METHOD_2}->execute($screen_name) != 0){
		return($B->{DBT_METHOD_2}->fetch()->[0]);
	}
	# needed undef, if return() DBI say ...
	# DBD::mysql::st execute failed: called with 6 bind variables when 7 are needed
	return(undef);
}

sub screen_name
{
	my($user_id) = @_;

	if($B->{DBT_METHOD_3}->execute($user_id) != 0){
		return($B->{DBT_METHOD_3}->fetch()->[0]);
	}elsif($B->{DBT_METHOD_4}->execute($user_id) != 0){
		return($B->{DBT_METHOD_4}->fetch()->[0]);
	}elsif($B->{DBT_METHOD_5}->execute($user_id) != 0){
		return($B->{DBT_METHOD_5}->fetch()->[0]);
	}
	return();
}

sub gzip
{
	return(Compress::Zlib::memGzip(nfreeze(shift())));
}

sub gunzip
{
	return(thaw(Compress::Zlib::memGunzip(shift())));
}

sub unpack_Structure
{
	my $g = shift();

	$g->{structure} = gunzip($g->{structure});
	return($g);
}

sub encode_MySQLTime
{
	my $DateTime = DateTime::Format::DateParse->parse_datetime(shift());
	$DateTime->set_time_zone($C->{_}->{TIMEZONE});
	$DateTime->set_locale(DateTime::Locale->load($C->{_}->{LOCALE}));
	return(DateTime::Format::MySQL->format_datetime($DateTime));
}

given(shift(@ARGV)){
	when("-qc"){
		printf("%s() : %d\n",$_,$B->{DBT_CLI_QC_0}->execute());
	}
	when("-qi"){
		sub get_queue
		{
			my $user_id = shift();
			my $order = shift() // "%";
			my $flag = shift() | F_QUEUE;

			if($B->{DBT_CLI_QI_0}->execute($user_id,$order,$flag,$flag) == 0){
				return();
			}
			return($B->{DBT_CLI_QI_0}->fetchrow_array());
		}
		sub new_queue
		{
			my $user_id = shift();
			my $screen_name = shift() // screen_name($user_id);
			my $order = shift() // "UNKNOWN.".uc((caller(0))[3]);
			my $priority = shift() // I_PRIORITY_MIDIUM;
			my $flag = shift() | F_QUEUE;

			if(!&get_queue($user_id,$order,$flag) && !$B->{DBT_CLI_QI_2}->execute($user_id,$screen_name,$order,$priority,$flag)){
				return();
			}
			return(1);
		}
		sub ini_queue
		{
			my $screen_name = shift();
			my $user_id = user_id($screen_name);

			if($user_id){
				#&new_queue($user_id,$screen_name,"UPDATE.TIMELINE",I_PRIORITY_HIGH,F_TWEETS);
				#&new_queue($user_id,$screen_name,"UPDATE.MENTION",I_PRIORITY_HIGH,F_REPLIES);
				#&new_queue($user_id,$screen_name,"UPDATE.FAVORITE",I_PRIORITY_HIGH,F_FAVORITES);
				&new_queue($user_id,$screen_name,"SALVAGE.TIMELINE",I_PRIORITY_HIGH,F_TWEETS);
				&new_queue($user_id,$screen_name,"SALVAGE.MENTION",I_PRIORITY_HIGH,F_REPLIES);
				&new_queue($user_id,$screen_name,"SALVAGE.RETWEETED",I_PRIORITY_HIGH,F_RETWEETED);
				&new_queue($user_id,$screen_name,"SALVAGE.FAVORITE",I_PRIORITY_HIGH,F_FAVORITES);
			}
			return($user_id);
		}

		printf("%s() : %d\n",$_,&ini_queue(@ARGV));
	}
	when("-ql"){
	}
	when("-qe"){
		sub mod_queue
		{
			my $id = shift();
			my $flag = shift();

			if($B->{DBT_CLI_QE_1}->execute($flag,$id) == 0){
				return();
			}
			return(1);
		}

		if($B->{DBT_CLI_QE_0}->execute() == 0){
			#return();
			exit(0);
		}
		my $r = $B->{DBT_CLI_QE_0}->fetchrow_hashref();

		local %SES;
		@SES{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)} = @{$r}{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)};

		&cb_prepare(
			[],
			[],
			[],
			{},
		);
		my $i = &salvage(
			[$r->{screen_name}],
			[$r->{screen_name}],
			[],
			{
				user_id =>$r->{user_id},
				flag =>$r->{flag} & F_API,
				axis =>{UPDATE =>1,SALVAGE =>-1}->{($r->{order} =~m/^(\w+)/o)[0]},
			},
		);

		$r->{priority} = I_PRIORITY_MIDIUM;
		if($i > 1){
			&mod_queue($r->{id},($r->{flag} & ~F_STATE) | F_FINISH);
			&new_queue(@{$r}{qw(user_id screen_name order priority flag)});
		}elsif($i == 1){
			&mod_queue($r->{id},($r->{flag} & ~F_STATE) | F_FINISH);
		}else{
			&mod_queue($r->{id},($r->{flag} & ~F_STATE) | F_FAILURE);
			&new_queue(@{$r}{qw(user_id screen_name order priority flag)});
		}

		printf("[Queue%d] Salvaged %d tweets.\n",$r->{id},$i);
	}
	when("-sd"){
		if($B->{DBT_CLI_SD_0}->execute(shift(@ARGV)) == 0){
			#return();
			die();
		}
		print Data::Dumper::Dumper(unpack_Structure($B->{DBT_CLI_SD_0}->fetchrow_hashref()));
	}
	when("--twilog"){
		for my $structure (keys(%{XMLin(shift(@ARGV))->{tweet}})){
			if($B->{SALVAGE_9}->execute($structure) == 0){
				print $structure."\n";
			}
		}
	}
	when(""){
		BlackCurtain::Ignorance->new(
			[
				[qr/./,\&cb_prepare],
				[qr/^\/?$/,\&cb_index],
				[qr/^\/(\w+)(?:\.([a-z]+))?(?:\/[fjr])?\/?$/,\&cb_show],
			],
			CGI::Session =>["driver:memcached",undef,{Memcached =>$B->{Cache::Memcached}}],
			Text::Xslate =>[path =>[split(/ /o,$C->{_}->{TEMPLATE})],cache_dir =>$C->{_}->{CACHE_DIR}],
		)->perform();
	}
	default{
	}
}
exit(0);

sub salvage
{
	sub bind
	{
		my $status_id = shift();
		my $referring_user_id = shift();
		my $referring_user_screen_name = shift();
		my $referred_user_id = shift();
		my $referred_user_screen_name = shift();
		my $flag = shift();

		if($B->{DBT_SALVAGE_7}->execute($status_id,$referring_user_id,$referring_user_screen_name,$referred_user_id,$referred_user_screen_name,$flag,$flag) > 0){
			return();
		}elsif($B->{DBT_SALVAGE_8}->execute($status_id,$referring_user_id,$referring_user_screen_name,$referred_user_id,$referred_user_screen_name,$flag,$flag) == 0){
			return();
		}
		return(1);
	}

	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name) = @{$q};
	my($screen_name,$issue) = @{$m};
	my($user_id,$flag,$axis) = @{$g}{qw(user_id flag axis)};
	$user_id //= user_id($screen_name);

	sub getedge
	{
		my $user_id = shift();
		my $flag = shift();
		my $axis = shift() >= 0 ? 1 : 0;

		my $g = $axis ? "since_id" : "max_id";
		my $i;
		given($flag){
			when(F_TWEETS){
				$i = $axis ? 0 : 1;
			}
			when(F_REPLIES){
				$i = $axis ? 2 : 3;
			}
			when(F_FAVORITES){
				$i = $axis ? 4 : 5;
			}
			when(F_RETWEETED){
				$i = $axis ? 0 : 1;
			}
		}
		if($B->{DBT_SALVAGE_.$i}->execute($g,$user_id,$flag,$flag) == 0){
			return();
		}
		return($B->{DBT_SALVAGE_.$i}->fetchrow_array());
	}

	my $r = [];
	given($flag){
		when(F_TWEETS){
			if(!($r = $B->{Net::Twitter}->user_timeline({id =>$user_id,&getedge($user_id,$flag,$axis),count =>200,include_entities =>1,include_rts =>1}))){
				return(-1);
			}
		}
		when(F_REPLIES){
			if(!($r = $B->{Net::Twitter}->mentions({id =>$user_id,&getedge($user_id,$flag,$axis),count =>200,include_entities =>1,include_rts =>1}))){
				return(-1);
			}
		}
		when(F_FAVORITES){
			if(!($r = $B->{Net::Twitter}->favorites({id =>$user_id,&getedge($user_id,$flag,$axis),count =>200,include_entities =>1,include_rts =>1}))){
				return(-1);
			}
		}
		when(F_RETWEETED){
			if(!($r = $B->{Net::Twitter}->retweets_of_me({id =>$user_id,&getedge($user_id,$flag,$axis),count =>200,include_entities =>1}))){
				return(-1);
			}
		}
		default{
			return(-1);
		}
	}

	for my $structure (@{$r}){
		$structure->{retweeted_by} = [];
		my $flag = $flag;
		my @flag;

		given($flag){
			when(F_TWEETS){
				if($structure->{text} =~ /^RT \@([0-9A-Za-z_]{1,15}):/o){
					push(@flag,F_RETWEETS);
					&bind(
						$structure->{id},
						$structure->{user}->{id},
						$structure->{user}->{screen_name},
						$structure->{retweeted_status}->{user}->{id} // undef,
						$structure->{retweeted_status}->{user}->{screen_name} // $1,
						$flag | F_RETWEETS,
					);
				}elsif($structure->{text} =~ /^(.+?)RT \@([0-9A-Za-z_]{1,15}):/o){
					push(@flag,F_RETWEETS);
					&bind(
						$structure->{id},
						$structure->{user}->{id},
						$structure->{user}->{screen_name},
						user_id($2),
						$2,
						$structure->{user}->{id} eq $user_id ? $flag | F_REGULAR | F_QUOTETWEETS : $flag | F_QUOTETWEETS,
					);
					for($1 =~m/\@([0-9A-Za-z_]{1,15})/go){
						push(@flag,F_REPLYTO);
						&bind(
							$structure->{id},
							$structure->{user}->{id},
							$structure->{user}->{screen_name},
							user_id($_),
							$_,
							$structure->{user}->{id} eq $user_id ? $flag | F_REGULAR | F_REPLYTO : $flag | F_REPLYTO,
						);
					}
				}else{
					for($structure->{text} =~m/\@([0-9A-Za-z_]{1,15})/go){
						push(@flag,F_REPLYTO);
						&bind(
							$structure->{id},
							$structure->{user}->{id},
							$structure->{user}->{screen_name},
							user_id($_),
							$_,
							$structure->{user}->{id} eq $user_id ? $flag | F_REGULAR | F_REPLYTO : $flag | F_REPLYTO,
						);
					}
				}
			}
			when(F_REPLIES){
				if($structure->{text} =~ /^RT \@$screen_name:/o){
					push(@flag,F_QUOTETWEETED);
					&bind(
						$structure->{id},
						$structure->{user}->{id},
						$structure->{user}->{screen_name},
						$user_id,
						$screen_name,
						$flag | F_QUOTETWEETED,
					);
				}elsif($structure->{text} =~ /^(.+?)RT \@$screen_name:/o){
					push(@flag,F_QUOTETWEETED);
					&bind(
						$structure->{id},
						$structure->{user}->{id},
						$structure->{user}->{screen_name},
						$user_id,
						$screen_name,
						$flag | F_QUOTETWEETED,
					);
				}else{
					&bind(
						$structure->{id},
						$structure->{user}->{id},
						$structure->{user}->{screen_name},
						$user_id,
						$screen_name,
						$flag,
					);
				}
			}
			when(F_FAVORITES){
				&bind(
					$structure->{id},
					$user_id,
					$screen_name,
					$structure->{user}->{id},
					$structure->{user}->{screen_name},
					$flag,
				);
			}
			when(F_RETWEETED){
				for my $i (0..15){
					my $r = $B->{Net::Twitter}->retweeted_by({id =>$structure->{id},count =>200,page =>$i,include_entities =>1});
					if(ref($r) && $#{$r} != -1){
						for(@{$r}){
							&bind(
								$structure->{id},
								$_->{id},
								$_->{screen_name},
								$structure->{user}->{id},
								$structure->{user}->{screen_name},
								$flag,
							);
						}
						push(@{$structure->{retweeted_by}},@{$r});
					}else{
						last();
					}
				}
			}
			default{
			}
		}

		for(@flag){
			$flag |= $_;
		}
		if($B->{DBT_SALVAGE_6}->execute(
			$structure->{id},
			$structure->{user}->{id},
			$structure->{user}->{screen_name},
			$structure->{text},
			encode_MySQLTime($structure->{created_at}),
			gzip({twitter =>$structure}),
			$structure->{user}->{id} eq $user_id ? $flag | F_REGULAR : $flag,
			$structure->{user}->{id} eq $user_id ? $flag | F_REGULAR : $flag,
		) == 0){
			return(-1);
		}
	}

	return($#{$r} + 1);
}

sub cb_prepare
{
	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name,$page) = @{$q};
	my($screen_name,$issue) = @{$m};

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

__END__

	}
}
exit(0);


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
			if($B->{STH_INDEX_0}->execute(@SES{qw(id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)}) == 0){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{screen_name},"SALVAGE.TIMELINE",I_PRIORITY_MIDIUM,F_QUEUE|F_TWEETS)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{screen_name},"SALVAGE.MENTION",I_PRIORITY_MIDIUM,F_QUEUE|F_REPLIES)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{screen_name},"SALVAGE.FAVORITE",I_PRIORITY_MIDIUM,F_QUEUE|F_FAVORITES)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
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

	my $r = {};
	my $sign = join(".",$C->{_}->{CACHE_PREFIX},$screen_name).".";
	if(!defined($r = $B->{Cache::Memcached}->get($sign."profile"))){
		if(!($r = $B->{Net::Twitter}->show_user({screen_name =>$screen_name}))){
			return(&cb_exception(undef,undef,undef,"ユーザ情報取得失敗"));
		}
		$B->{Cache::Memcached}->set($sign."profile",$r,$C->{_}->{CACHE_EXPIRE});
	}

	if(!defined($page)){
		if(!defined($r->{status} = $B->{Cache::Memcached}->get($sign."timeline"))){
			#if(!($r->{status} = &salvage(undef,$m,undef,[2,1]))){
			#	return(&cb_exception(undef,undef,undef,"ユーザ情報取得失敗"));
			#}
			#$B->{Cache::Memcached}->set($sign."timeline",$r->{status},$C->{_}->{CACHE_EXPIRE});
		}
	}elsif($page eq "j"){
		if($B->{STH_SHOW_0}->execute($r->{screen_name})){
			map{$_->{description} = $C->{QueueDescription}->{uc($_->{order})}}@{$r->{_queue} = $B->{STH_SHOW_0}->fetchall_arrayref({})};
		}
	}

	return($issue ? $issue : "Text::Xslate",$r,data =><<'EOF');
<html>
<head>
<title>ついっとったー</title>
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
