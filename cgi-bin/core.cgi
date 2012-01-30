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
use Calendar::Simple;
use constant F_NULL =>0;
use constant F_QUEUE =>1 << 0;
use constant F_PROCESS =>1 << 1;
use constant F_FINISH =>1 << 2;
use constant F_FAILURE =>1 << 3;
use constant F_STOP =>1 << 4;
use constant F_STATE =>F_QUEUE|F_PROCESS|F_FINISH|F_FAILURE|F_STOP;
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
use constant F_FAVORITED =>1 << 16;
use constant F_SYNCHRONIZED =>1 << 17;
use constant F_TIMELINE =>1 << 18;
use constant F_API_MASK =>F_TWEETS|F_REPLIES|F_FAVORITES|F_RETWEETED|F_TIMELINE;
use constant F_TYPE_MASK =>F_API_MASK|F_RETWEETS|F_QUOTETWEETS|F_REPLYTO|F_QUOTETWEETED|F_FAVORITED;
use constant I_PRIORITY_LOW =>1;
use constant I_PRIORITY_MIDIUM =>2;
use constant I_PRIORITY_HIGH =>3;

BEGIN
{
	$C = Config::Tiny->read_string(<<'EOF');
TIMEZONE=Asia/Tokyo
LOCALE=ja_JP

CACHE_DIR=/tmp
CACHE_PREFIX=twittotter
TEMPLATE=/var/www/twittotter/html

LIMIT=48

[Cache]
DEFAULT_EXPIRE=3600
PROFILE_EXPIRE=7200
STATIC_STATUS_EXPIRE=7200
STATUS_EXPIRE=1800
QUEUE_EXPIRE=0

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
CLI_QI_2=INSERT `Queue` (`user_id`,`screen_name`,`order`,`priority`,`atime`,`flag`) VALUES(?,?,?,?,DATE_ADD(CURRENT_TIMESTAMP,INTERVAL ? SECOND),?)
CLI_QE_0=SELECT * FROM `Queue` LEFT JOIN `Token` ON `Queue`.`user_id` = `Token`.`user_id` WHERE `atime` <= CURRENT_TIMESTAMP AND `flag` & 1 ORDER BY `Queue`.`priority` DESC,`Queue`.`ctime` ASC LIMIT 0,1
CLI_QE_1=UPDATE `Queue` SET `flag` = ?,`mtime` = CURRENT_TIMESTAMP WHERE `id` = ?
SALVAGE_0=SELECT ?,`status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` DESC LIMIT 0,1
SALVAGE_1=SELECT ?,`status_id` - 1 AS `status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` ASC LIMIT 0,1
SALVAGE_2=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_3=SELECT ?,`Tweet`.`status_id` - 1 AS `status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
SALVAGE_4=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_5=SELECT ?,`Tweet`.`status_id` - 1 AS `status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
SALVAGE_6=INSERT `Tweet` (`status_id`,`user_id`,`screen_name`,`text`,`created_at`,`structure`,`flag`) VALUES (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `flag` = `flag` | ?
SALVAGE_7=SELECT 1 FROM `Bind` WHERE `status_id` = ? AND (`referring_user_id` = ? OR `referring_screen_name` = ?) AND (`referred_user_id` = ? OR `referred_screen_name` = ?) AND `flag` & ? = ?
SALVAGE_8=INSERT `Bind` (`status_id`,`referring_user_id`,`referring_screen_name`,`referred_user_id`,`referred_screen_name`,`flag`) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `flag` = `flag` | ?
SALVAGE_9=UPDATE `Bind` SET `flag` = ? WHERE `status_id` = ? AND (`referring_user_id` = ? OR `referring_screen_name` = ?) AND (`referred_user_id` = ? OR `referred_screen_name` = ?) AND `flag` & ? = ?
SALVAGE_10=SELECT * FROM `Tweet` WHERE `status_id` = ? LIMIT 0,1
SALVAGE_11=INSERT `Tweet` (`status_id`,`user_id`,`screen_name`,`text`,`created_at`,`structure`,`flag`) VALUES (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `structure` = VALUES(`structure`),`flag` = `flag` | ?
SALVAGE_12=SELECT `flag` FROM `Tweet` WHERE `status_id` = ? LIMIT 0,1

INDEX_0=INSERT `Token` (`user_id`,`screen_name`,`ACCESS_TOKEN`,`ACCESS_TOKEN_SECRET`) VALUES(?,?,?,?) ON DUPLICATE KEY UPDATE `ctime` = CURRENT_TIMESTAMP
SHOW_0=SELECT * FROM `Queue` WHERE `user_id` = ? OR `screen_name` = ? ORDER BY `ctime` DESC LIMIT 0,48
SHOW_1=SELECT COUNT(*) FROM `Queue` WHERE `user_id` = ? OR `screen_name` = ? ORDER BY `ctime` DESC LIMIT 0,48
SHOW_2=SELECT *,COUNT(*) as `i` FROM `Bind` WHERE (`referred_user_id` = ? OR `referred_screen_name` = ?) AND `flag` & ? = ? GROUP BY `referring_screen_name` ORDER BY `i` DESC LIMIT 0,8
SHOW_3=SELECT *,COUNT(*) as `i` FROM `Bind` WHERE (`referring_user_id` = ? OR `referring_screen_name` = ?) AND `flag` & ? = ? GROUP BY `referred_screen_name` ORDER BY `i` DESC LIMIT 0,8
SHOW_5=SELECT DATE_FORMAT(`created_at`,'%Y-%m') as `created_at_ym`,COUNT(*) as `i` FROM `Tweet` WHERE `user_id` = ? OR `screen_name` = ? GROUP BY `created_at_ym` ORDER BY `created_at_ym` DESC
SEARCH_0=SELECT FOUND_ROWS()
SEARCH_0_NP=SELECT SQL_CALC_FOUND_ROWS DISTINCT `Tweet`.`status_id`,`Tweet`.`structure` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE ({}) AND ({}) AND {} ORDER BY `Tweet`.`created_at` DESC LIMIT {},{}
SEARCH_1_NP=(`Tweet`.`user_id` = ? OR `Tweet`.`screen_name` = ?)
SEARCH_2_NP=((`Bind`.`referring_user_id` = ? OR `Bind`.`referring_screen_name` = ?) AND `Bind`.`flag` & ? = ?)
SEARCH_3_NP=((`Bind`.`referred_user_id` = ? OR `Bind`.`referred_screen_name` = ?) AND `Bind`.`flag` & ? = ?)
SEARCH_4_NP=`Tweet`.`text` = ?
SEARCH_5_NP=`Tweet`.`text` LIKE ?
SEARCH_6_NP=`Tweet`.`text` REGEXP ?
SEARCH_7_NP=YEAR(`Tweet`.`created_at`) = ?
SEARCH_8_NP=MONTH(`Tweet`.`created_at`) = ?
SEARCH_9_NP=DAY(`Tweet`.`created_at`) = ?

[Memcached]
HOST=127.0.0.1:11211

[QueueDescription]
SALVAGE.TIMELINE=過去のツイート取得 (200件)
SALVAGE.MENTION=過去のリプライ取得 (200件)
SALVAGE.RETWEETED=過去のリツイート取得 (200件)
SALVAGE.FAVORITE=過去のお気に入り取得 (200件)

EOF
	$B = {
		DBI =>DBI->connect(sprintf("dbi:mysql:database=%s;host=%s;port=%d",@{$C->{MySQL}}{qw(DATABASE HOST PORT)}),@{$C->{MySQL}}{qw(USERNAME PASSWORD)}),
		Cache::Memcached =>Cache::Memcached::libmemcached->new({servers =>[split(/ /o,$C->{Memcached}->{HOST})]}),
	};
	for(grep(/_[0-9]+$/ && !/_NP$/o,keys(%{$C->{MySQL}}))){
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

sub unpack_structure
{
	my $g = shift() // $_;

	$g->{structure} = gunzip($g->{structure});
	return($g);
}


sub encode_DateTime
{
	my $DateTime = DateTime::Format::DateParse->parse_datetime(shift());
	$DateTime->set_time_zone($C->{_}->{TIMEZONE});
	$DateTime->set_locale(DateTime::Locale->load($C->{_}->{LOCALE}));
	return($DateTime);
}

sub encode_MySQLTime
{
	return(DateTime::Format::MySQL->format_datetime(encode_DateTime(shift())));
}

if(defined($ENV{GATEWAY_INTERFACE})){
	BlackCurtain::Ignorance->new(
		[
			[qr/./,\&cb_prepare],
			[qr/^\/?$/,\&cb_index],
			[qr/^\/(\w+)(?:\.([a-z]+))?(?:\/([a-z]+))?(?:\/(\d{4})(?:\-(\d{1,2})(?:\-(\d{1,2}))?)?)?(?:\/(\d+))?\/?$/,\&cb_show],
		],
		CGI::Session =>["driver:memcached",undef,{Memcached =>$B->{Cache::Memcached}}],
		Text::Xslate =>[path =>[split(/ /o,$C->{_}->{TEMPLATE})],cache_dir =>$C->{_}->{CACHE_DIR},module =>[qw(Text::Xslate::Bridge::Star Calendar::Simple)]],
	)->perform();
}else{


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
			my $atime = shift() // 0;
			my $flag = shift() | F_QUEUE;

			if(!&get_queue($user_id,$order,$flag) && !$B->{DBT_CLI_QI_2}->execute($user_id,$screen_name,$order,$priority,$atime,$flag)){
				return();
			}
			return(1);
		}
		sub ini_queue
		{
			my $screen_name = shift();
			my $user_id = user_id($screen_name);

			if($user_id){
				#&new_queue($user_id,$screen_name,"SALVAGE.TIMELINE",I_PRIORITY_HIGH,0,F_TWEETS);
				#&new_queue($user_id,$screen_name,"SALVAGE.MENTION",I_PRIORITY_HIGH,0,F_REPLIES);
				#&new_queue($user_id,$screen_name,"SALVAGE.RETWEETED",I_PRIORITY_HIGH,0,F_RETWEETED);
				#&new_queue($user_id,$screen_name,"SALVAGE.FAVORITE",I_PRIORITY_HIGH,0,F_FAVORITES);
				#&new_queue($user_id,$screen_name,"UPDATE.TIMELINE",I_PRIORITY_HIGH,0,F_TWEETS);
				#&new_queue($user_id,$screen_name,"UPDATE.MENTION",I_PRIORITY_HIGH,0,F_REPLIES);
				#&new_queue($user_id,$screen_name,"UPDATE.FAVORITE",I_PRIORITY_HIGH,0,F_FAVORITES);
				#&new_queue($user_id,$screen_name,"UPDATE.RETWEETED",I_PRIORITY_HIGH,0,F_RETWEETED);
				&new_queue($user_id,$screen_name,"UPDATE.TIMELINE.ALL",I_PRIORITY_LOW,0,F_TIMELINE);
				#&new_queue($user_id,$screen_name,"COMPARE.TIMELINE",I_PRIORITY_HIGH,0,F_TWEETS);
				#&new_queue($user_id,$screen_name,"COMPARE.MENTION",I_PRIORITY_HIGH,0,F_REPLIES);
				#&new_queue($user_id,$screen_name,"COMPARE.RETWEETED",I_PRIORITY_HIGH,0,F_RETWEETED);
				#&new_queue($user_id,$screen_name,"COMPARE.FAVORITE",I_PRIORITY_HIGH,0,F_FAVORITES);
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
				flag =>$r->{flag} & F_API_MASK,
				axis =>{UPDATE =>1,SALVAGE =>-1,COMPARE =>-1}->{($r->{order} =~m/^(\w+)/o)[0]},
			},
		);

		if($r->{order} =~ /^(?:UPDATE)/io){
			$r->{priority} = I_PRIORITY_LOW;
			$r->{atime} = 1200;
			&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
			&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
		}elsif($i != 0){
			$r->{priority} = I_PRIORITY_MIDIUM;
			$r->{atime} = 600;
			&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
			&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
		}else{
			&mod_queue($r->{id},($r->{flag} & ~F_STATE) | F_FINISH);
		}

		printf("[Queue%d] Salvaged %d tweets.\n",$r->{id},$i);
	}
	when("-sd"){
		if($B->{DBT_CLI_SD_0}->execute(shift(@ARGV)) == 0){
			#return();
			die();
		}
		print Data::Dumper::Dumper(unpack_structure($B->{DBT_CLI_SD_0}->fetchrow_hashref()));
	}
	when("--twilog"){
		for my $structure (keys(%{XMLin(shift(@ARGV))->{tweet}})){
			if($B->{SALVAGE_10}->execute($structure) == 0){
				print $structure."\n";
			}
		}
	}
	when(""){
	}
	default{
	}
}
}
exit(0);

sub salvage
{
	sub bind
	{
		my $status_id = shift();
		my $referring_user_id = shift();
		my $referring_screen_name = shift();
		my $referred_user_id = shift();
		my $referred_screen_name = shift();
		my $flag = shift();

		if($B->{DBT_SALVAGE_7}->execute($status_id,$referring_user_id,$referring_screen_name,$referred_user_id,$referred_screen_name,$flag & F_TYPE_MASK,$flag & F_TYPE_MASK) > 0){
			if($B->{DBT_SALVAGE_9}->execute($flag,$status_id,$referring_user_id,$referring_screen_name,$referred_user_id,$referred_screen_name,$flag & F_TYPE_MASK,$flag & F_TYPE_MASK) == 0){
				return();
			}
		}else{
			if($B->{DBT_SALVAGE_8}->execute($status_id,$referring_user_id,$referring_screen_name,$referred_user_id,$referred_screen_name,$flag,$flag) == 0){
				return();
			}
		}
		return(1);
	}
	sub edge
	{
		my $user_id = shift();
		my $flag = shift();
		my $axis = shift() >= 0 ? 1 : 0;

		my $g = $axis ? "since_id" : "max_id";
		my $i;
		given($flag & F_API_MASK){
			when(F_TWEETS){
				$i = $axis ? 0 : 1;
			}
			when(F_REPLIES){
				$i = $axis ? 2 : 3;
			}
			when(F_RETWEETED){
				$i = $axis ? 0 : 1;
			}
			when(F_FAVORITES){
				$i = $axis ? 4 : 5;
			}
			when(F_TIMELINE){
				$i = $axis ? 4 : 5;
			}
		}
		if($B->{DBT_SALVAGE_.$i}->execute($g,$user_id,$flag,$flag) == 0){
			return();
		}
		return($B->{DBT_SALVAGE_.$i}->fetchrow_array());
	}

	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name) = @{$q};
	my($screen_name,$issue) = @{$m};
	my($user_id,$flag,$axis) = @{$g}{qw(user_id flag axis)};
	$user_id //= user_id($screen_name);
	$flag = $flag | F_SYNCHRONIZED;

	my $r = [];
	given($flag & F_API_MASK){
		when(F_TWEETS){
			if(!($r = $B->{Net::Twitter}->user_timeline({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,include_entities =>1,include_rts =>1}))){
				return(-1);
			}
		}
		when(F_REPLIES){
			if(!($r = $B->{Net::Twitter}->mentions({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,include_entities =>1,include_rts =>1}))){
				return(-1);
			}
		}
		when(F_RETWEETED){
			if(!($r = $B->{Net::Twitter}->retweets_of_me({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,include_entities =>1}))){
				return(-1);
			}
		}
		when(F_FAVORITES){
			if(!($r = $B->{Net::Twitter}->favorites({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,include_entities =>1,include_rts =>1}))){
				return(-1);
			}
		}
		when(F_TIMELINE){
			if(!($r = $B->{Net::Twitter}->friends_timeline({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,include_entities =>1,include_rts =>1}))){
				return(-1);
			}
		}
		default{
			return(-1);
		}
	}

	for my $structure (@{$r}){
		$structure->{retweeted_by} = [];
		my $flag = $structure->{user}->{id} eq $user_id ? $flag | F_REGULAR : $flag;
		my @flag;

		given($flag & F_API_MASK){
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
					push(@flag,F_QUOTETWEETS);
					&bind(
						$structure->{id},
						$structure->{user}->{id},
						$structure->{user}->{screen_name},
						user_id($2),
						$2,
						$flag | F_QUOTETWEETS,
					);
					for($1 =~m/\@([0-9A-Za-z_]{1,15})/go){
						push(@flag,F_REPLYTO);
						&bind(
							$structure->{id},
							$structure->{user}->{id},
							$structure->{user}->{screen_name},
							user_id($_),
							$_,
							$flag | F_REPLYTO,
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
							$flag | F_REPLYTO,
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
			when(F_RETWEETED){
				for my $i (0..15){
					my $r;
					if(!($r = $B->{Net::Twitter}->retweeted_by({id =>$structure->{id},count =>200,page =>$i,include_entities =>1}))){
						return(-1);
					}
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
			when(F_TIMELINE){
				&bind(
					$structure->{id},
					$user_id,
					$screen_name,
					$structure->{user}->{id},
					$structure->{user}->{screen_name},
					$flag,
				);

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
					push(@flag,F_QUOTETWEETS);
					&bind(
						$structure->{id},
						$structure->{user}->{id},
						$structure->{user}->{screen_name},
						user_id($2),
						$2,
						$flag | F_QUOTETWEETS,
					);
					for($1 =~m/\@([0-9A-Za-z_]{1,15})/go){
						push(@flag,F_REPLYTO);
						&bind(
							$structure->{id},
							$structure->{user}->{id},
							$structure->{user}->{screen_name},
							user_id($_),
							$_,
							$flag | F_REPLYTO,
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
							$flag | F_REPLYTO,
						);
					}
				}
			}
			default{
			}
		}

		for(@flag){
			$flag |= $_;
		}

		my $inserted_flag = 0;
		if($B->{DBT_SALVAGE_12}->execute($structure->{id}) != 0){
			$inserted_flag = ($B->{DBT_SALVAGE_12}->fetchrow_array())[0] // 0;
		}
		if($flag & F_REGULAR && !($inserted_flag & F_RETWEETED)){
			if($B->{DBT_SALVAGE_11}->execute(
				$structure->{id},
				$structure->{user}->{id},
				$structure->{user}->{screen_name},
				$structure->{text},
				encode_MySQLTime($structure->{created_at}),
				gzip({twitter =>$structure}),
				$flag,
				$flag,
			) == 0){
				return(-1);
			}
		}else{
			if($B->{DBT_SALVAGE_6}->execute(
				$structure->{id},
				$structure->{user}->{id},
				$structure->{user}->{screen_name},
				$structure->{text},
				encode_MySQLTime($structure->{created_at}),
				gzip({twitter =>$structure}),
				$flag,
				$flag,
			) == 0){
				return(-1);
			}
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

	my $time = time();
	my @time = localtime($time);
	$SES{u} = $time;
	$SES{s} = $time[0];
	$SES{n} = $time[1];
	$SES{h} = $time[2];
	$SES{d} = $time[3];
	$SES{m} = $time[4] + 1;
	$SES{y} = $time[5] + 1900;
	$SES{w} = $time[6];

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
<title>ついっとったー</title>
<body>
<p><a href="/?op=login">login</a></p>
<p><a href="/?op=logout">logout</a></p>
<p><a href="/el1n">こんな感じ</a></p>
</body>
</html>
EOF
	}elsif($GET{op} eq "login" && $GET{oauth_token} && $GET{oauth_verifier}){
		$B->{Net::Twitter}->request_token($SES{REQUEST_TOKEN});
		$B->{Net::Twitter}->request_token_secret($SES{REQUEST_TOKEN_SECRET});
		@SES{qw(ACCESS_TOKEN ACCESS_TOKEN_SECRET user_id screen_name)} = $B->{Net::Twitter}->request_access_token(token =>$GET{oauth_token},verifier =>$GET{oauth_verifier});
		if($SES{user_id} > 0){
			if($B->{DBT_INDEX_0}->execute(@SES{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)}) == 0){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"SALVAGE.TIMELINE",I_PRIORITY_HIGH,0,F_QUEUE|F_TWEETS)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"SALVAGE.MENTION",I_PRIORITY_HIGH,0,F_QUEUE|F_REPLIES)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"SALVAGE.RETWEETED",I_PRIORITY_HIGH,0,F_QUEUE|F_RETWEETED)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"SALVAGE.FAVORITE",I_PRIORITY_HIGH,0,F_QUEUE|F_FAVORITES)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"UPDATE.TIMELINE",I_PRIORITY_HIGH,0,F_QUEUE|F_TWEETS)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"UPDATE.MENTION",I_PRIORITY_HIGH,0,F_QUEUE|F_REPLIES)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"UPDATE.RETWEETED",I_PRIORITY_HIGH,0,F_QUEUE|F_RETWEETED)){
				return(&cb_exception(undef,undef,undef,{msg =>"認証失敗"}));
			}elsif(!&new_queue($SES{user_id},$SES{screen_name},"UPDATE.FAVORITE",I_PRIORITY_HIGH,0,F_QUEUE|F_FAVORITES)){
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
	$m->[2] //= "t";
	my $d = shift();
	my $g = shift();
	my($screen_name) = @{$q};
	my($screen_name,$issue,$clause,@g) = @{$m};
	$m->[3] //= $GET{y};
	$m->[4] //= $GET{m};
	$m->[5] //= $GET{d};
	my $user_id = user_id($screen_name);
	$clause .= $GET{c};

	my $r;
	my $sign = join(".",$C->{_}->{CACHE_PREFIX},$screen_name).".";
	if(!defined($r = $B->{Cache::Memcached}->get($sign."profile"))){
		if(!($r = $B->{Net::Twitter}->show_user({screen_name =>$screen_name}))){
			return(&cb_exception(undef,undef,undef,"ユーザ情報取得失敗"));
		}

		if($B->{DBT_SHOW_2}->execute($user_id,$screen_name,F_REPLIES,F_REPLIES)){
			$r->{"count_".F_REPLIES} = $B->{DBT_SHOW_2}->fetchall_arrayref({});
		}
		if($B->{DBT_SHOW_3}->execute($user_id,$screen_name,F_REPLYTO,F_REPLYTO)){
			$r->{"count_".F_REPLYTO} = $B->{DBT_SHOW_3}->fetchall_arrayref({});
		}
		if($B->{DBT_SHOW_5}->execute($user_id,$screen_name)){
			$r->{"archives"} = $B->{DBT_SHOW_5}->fetchall_arrayref({});
		}

		$B->{Cache::Memcached}->set($sign."profile",$r,$C->{Cache}->{PROFILE_EXPIRE});
	}
	$r->{IS_SEARCH} = length($clause) == 1 && $clause =~ /^[zjtmrequfa]$/o && !defined($GET{grep}) && !defined($GET{egrep}) && !defined($g[0]) ? 0 : 1;
	$r->{STATIC} = length($clause) == 1 && $clause =~ /^[zjtmrequfa]$/o && !defined($GET{grep}) && !defined($GET{egrep}) && !defined($g[0]) && !defined($g[3]) ? 1 : 0;

	sub prepare_structure
	{
		my $g = shift() // $_;

		unpack_structure($g);
		$g = $g->{structure}->{twitter};

		for(@{$g->{entities}->{urls}}){
			if(defined($_->{expanded_url})){
				#$g->{text} =~s/$_->{url}/$_->{expanded_url}/g;
				$g->{text} =~s/$_->{url}/<a href="$_->{expanded_url}" target="_blank">$_->{expanded_url}<\/a>/g;
			}else{
				$g->{text} =~s/$_->{url}/<a href="$_->{url}" target="_blank">$_->{url}<\/a>/g;
			}
		}
		#$g->{text} =~s/((?:ht|f)tps?:\/{2}[^\/]+\/[\x21-\x7E]+)/<a href="$1" target="_blank">$1<\/a>/g;
		$g->{text} =~s/(#\w+)/<a href="https:\/\/twitter.com\/#!\/search\/$1" target="_blank">$1<\/a>/g;
		$g->{text} =~s/^RT \@([0-9A-Za-z_]{1,15}):/RT <a href="https:\/\/twitter.com\/#!\/$1" target="_blank">\@$1<\/a>&nbsp;<a href="https:\/\/twitter.com\/#!\/$1\/status\/$g->{retweeted_status}->{id}" target="_blank">&raquo;<\/a>:/g;
		$g->{text} =~s/^\@([0-9A-Za-z_]{1,15})/<a href="https:\/\/twitter.com\/#!\/$1" target="_blank">\@$1<\/a>&nbsp;<a href="https:\/\/twitter.com\/#!\/$1\/status\/$g->{in_reply_to_status_id}" target="_blank">&raquo;<\/a>/g;
		$g->{text} =~s/(?<!>)\@([0-9A-Za-z_]{1,15})/<a href="https:\/\/twitter.com\/#!\/$1" target="_blank">\@$1<\/a>/g;

		$g->{created_at_formatted} = encode_DateTime($g->{created_at})->strftime("%Y-%m-%d %H:%M");

		return($g);
	}

	if($clause eq "j"){
		if(!defined($r->{status} = $B->{Cache::Memcached}->get($sign.$clause))){
			if(!$B->{DBT_SHOW_0}->execute($user_id,$screen_name)){
			}
			map{
1;
			}@{$r->{queue} = $B->{DBT_SHOW_0}->fetchall_arrayref({})};
			if(!$B->{DBT_SHOW_1}->execute($user_id,$screen_name)){
			}
			push(@{$r->{queue}},($B->{DBT_SEARCH_0}->fetchrow_array())[0]);
			$B->{Cache::Memcached}->set($sign.$clause,$r->{queue},$C->{Cache}->{QUEUE_EXPIRE});
		}
	}elsif(!$r->{STATIC} || !defined($r->{status} = $B->{Cache::Memcached}->get($sign.$clause))){
		my @where_time;
		my @where_base;
		my @where_char;
		my @bind;

		for my $i (0..2){
			if($g[$i] > 0){
				push(@where_time,$C->{MySQL}->{SEARCH_.(7 + $i)._NP});
				push(@bind,$g[$i]);
			}
		}
		for(qw(t m r e q u f a i)){
			if($clause =~ /$_/){
				my($i,$l,$flag) = @{{
					t =>[1,2,F_TWEETS],
					m =>[3,4,F_REPLIES],
					_ =>[2,4,F_REPLYTO],
					r =>[2,4,F_RETWEETS],
					e =>[3,4,F_RETWEETED],
					q =>[2,4,F_QUOTETWEETS],
					u =>[3,4,F_QUOTETWEETED],
					f =>[2,4,F_FAVORITES],
					a =>[3,4,F_FAVORITED],
					i =>[2,4,F_TIMELINE],
				}->{$_}};

				push(@where_base,$C->{MySQL}->{SEARCH_.$i._NP});
				push(@bind,($user_id,$screen_name,$flag,$flag)[0..$l - 1]);
			}
		}
		for(split(/\s+/o,$GET{grep})){
			push(@where_char,$C->{MySQL}->{SEARCH_5_NP});
			push(@bind,"%".$_."%");
		}
		if(defined($GET{egrep})){
			push(@where_char,$C->{MySQL}->{SEARCH_6_NP});
			push(@bind,$GET{egrep});
		}

		my @embed = (
			$#where_time != -1 ? join(" AND ",@where_time) : 1,
			$#where_base != -1 ? join(" OR ",@where_base) : 0,
			$#where_char != -1 ? join(" AND ",@where_char) : 1,
			$g[3] < 1 ? 0 : ($g[3] - 1) * $C->{_}->{LIMIT},
			$C->{_}->{LIMIT},
		);

		my $query = $C->{MySQL}->{SEARCH_0_NP};
		for(@embed){
			$query =~s/{}/$_/o;
		}
		map{$_ = prepare_structure($_)}@{$r->{status} = $B->{DBI}->selectall_arrayref($query,{Slice =>{}},@bind)};
		$B->{DBT_SEARCH_0}->execute();
		push(@{$r->{status}},($B->{DBT_SEARCH_0}->fetchrow_array())[0]);

		if($r->{STATIC}){
			$B->{Cache::Memcached}->set($sign.$clause,$r->{status},$C->{Cache}->{STATIC_STATUS_EXPIRE});
		}
	}
	$r->{rows} = pop(@{$r->{status}});

	return($issue ? $issue : "Text::Xslate",$r // {},data =><<'EOF');
: constant SCREEN = 800
: constant FONT_SIZE = 10
: constant MENU_WIDTH = 159
: constant TAB_WIDTH = 136
<html>
<head>
<title>ついっとったー</title>
<style type="text/css">
body {
	color:#<:$profile_text_color:>;
	background-color:#<:$profile_background_color:>;
	font-size:<:FONT_SIZE:>pt;
	font-family:"Verdana";
}
a:link,a:visited,a:hover,a:active {
	color:#<:$profile_link_color:>;
	text-decoration:none;
}

table
{
	margin:12px auto 0px auto;
}

th,td {
	border-right:solid 1px #<:$profile_sidebar_border_color:>;
	border-bottom:solid 1px #<:$profile_sidebar_border_color:>;
	font-size:<:FONT_SIZE:>pt;
}

.line {
	border:solid 1px #FF0000;
}
.pile {
	float:right;
}
.cl {
	clear:both;
}

.overall {
	margin:12px auto 0px auto;
	width:<:SCREEN:>px;
	border:solid 1px #<:$profile_sidebar_border_color:>;
	background-color:#FFFFFF;
}
.menu {
	margin:0px 0px 0px 0px;
	padding:0px 0px 8px 0px;
	width:<:MENU_WIDTH:>px;
	border-left:solid 1px #<:$profile_sidebar_border_color:>;
	border-bottom:solid 1px #<:$profile_sidebar_border_color:>;
	background-color:#<:$profile_sidebar_fill_color:>;
}
.form {
	margin:0px 0px 0px 0px;
	padding:8px 4px 8px 4px;
	width:<:MENU_WIDTH - 8:>px;
	border-left:solid 1px #<:$profile_sidebar_border_color:>;
	border-bottom:solid 1px #<:$profile_sidebar_border_color:>;
	background-color:#<:$profile_sidebar_fill_color:>;
}
.inf
{
	margin:0px 2px 24px 4px;
	padding:0px 0px 0px 0px;
}
.img
{
	margin:4px 4px 4px 4px;
	padding:0px 0px 0px 0px;
	border:solid 1px #<:$profile_sidebar_border_color:>;
}
.tab
{
	margin:0px <:MENU_WIDTH - TAB_WIDTH:>px -1px -1px;
	padding:4px 0px 4px 16px;
	border:solid 1px #<:$profile_sidebar_border_color:>;
}
.act
{
	border-left:solid 1px #FFFFFF;
	background-color:#FFFFFF;
}
.calendar table {
}
.calendar th,.calendar td {
	width:16px;
	text-align:center;
	font-size:<:FONT_SIZE - 1:>pt;
	font-weight:normal;
}
.calendar td {
	background-color:#FFFFFF;
}
.main {
	margin:0px 0px 0px 0px;
	padding:0px 0px 0px 0px;
	width:<:SCREEN - MENU_WIDTH - 3:>px;
	background-color:#FFFFFF;
}
.search_form {
	margin:8px 8px 8px 8px;
	padding:12px 8px 0px 8px;
	border:solid 1px #<:$profile_sidebar_border_color:>;
	background-color:#<:$profile_sidebar_fill_color:>;
}
.timeline_name {
	margin:0px 8px 0px 4px;
	padding:2px 0px 2px 0px;
}
.timeline_text {
	margin:0px 24px 0px 8px;
	padding:0px 0px 2px 0px;
	border-bottom:solid 1px #<:$profile_sidebar_border_color:>;
}
.page {
	width:24px;
	text-align:center;
}
.screen_name {
	color:#333333;
	font-weight:bold;
}
.name {
	color:#666666;
}
.created_at,.id {
	color:#999999;
	font-size:<:FONT_SIZE - 2:>pt;
}
</style>
</head>
<body>
<div class="overall">
	<div class="pile">
	<div class="menu">
		<div class="img pile"><img src="<:$profile_image_url:>"></div>
		<div class="inf">
			<span id="name"><:$name:></span><br>
			&nbsp;&nbsp;#<span id="id"><:$id:></span><br>
			&nbsp;&nbsp;@<span id="screen_name"><:$screen_name:></span><br>
		</div>
		<div class="tab<:$STATIC && $MATCH[2] == "t" ? " act" : "":>"><a href="/<:$screen_name:>">ついっと</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "m" ? " act" : "":>"><a href="/<:$screen_name:>/m">@<:$screen_name:></a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "r" ? " act" : "":>"><a href="/<:$screen_name:>/r">りついっと した</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "e" ? " act" : "":>"><a href="/<:$screen_name:>/e">りついっと された</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "q" ? " act" : "":>"><a href="/<:$screen_name:>/q">くおとついっと した</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "u" ? " act" : "":>"><a href="/<:$screen_name:>/u">くおとついっと された</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "f" ? " act" : "":>"><a href="/<:$screen_name:>/f"><span style="color: yellow;">&#9733;</span> した</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "a" ? " act" : "":>"><a href="/<:$screen_name:>/a"><span style="color: yellow;">&#9733;</span> された</a></div>
		<div class="tab<:!$STATIC ? " act" : "":>"><a href="/<:$screen_name:>/s">けんさく</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "z" ? " act" : "":>"><a href="/<:$screen_name:>/z">なにか</a></div>
		<div class="tab<:$STATIC && $MATCH[2] == "j" ? " act" : "":>"><a href="/<:$screen_name:>/j">きゅー</a></div>
		<table class="calendar">
			<tr>
				<th><a href="/<:$screen_name:>/<:$MATCH[2]:>/<:$MATCH[4] != 1 ? $MATCH[3] : $MATCH[3] - 1:>-<:$MATCH[4] != 1 ? $MATCH[4] - 1 : 12:>">&lt;</a></th>
				<th colspan="5"><:$MATCH[3]:>-<:$MATCH[4]:></th>
				<th><a href="/<:$screen_name:>/<:$MATCH[2]:>/<:$MATCH[4] != 12 ? $MATCH[3] : $MATCH[3] + 1:>-<:$MATCH[4] != 12 ? $MATCH[4] + 1 : 1:>">&gt;</a></th>
			</tr>
			<tr>
				<th>日</th>
				<th>月</th>
				<th>火</th>
				<th>水</th>
				<th>木</th>
				<th>金</th>
				<th>土</th>
			</tr>
:for calendar($MATCH[4],$MATCH[3]) -> $i {
			<tr>
:for $i -> $i {
				<td><a href="/<:$screen_name:>/<:$MATCH[2]:>/<:$MATCH[3]:>-<:$MATCH[4]:>-<:$i:>"><:$i:></a></td>
:}
			</tr>
:}
		</table>
		<div class="">
			<ul>
:for $archives -> $e {
				<li><a href="/<:$screen_name:>/t/<:$e.created_at_ym:>"><:$e.created_at_ym:></a> (<:$e.i:>)</li>
:}
			</ul>
		</div>
	</div>
	<div class="">
		<img src="/img/a.png">
	</div>
	</div>
	<div class="main pile">
:if $MATCH[2] == "z" {
:}elsif $MATCH[2] == "j" {
		<table>
			<tr>
				<th></th>
				<th>実行予定時</th>
				<th>実行時</th>
				<th>内容</th>
				<th>優先度</th>
				<th>状態</th>
			</tr>
:for $queue -> $queue {
			<tr>
				<td><:$queue.id:></td>
				<td><:$queue.atime:></td>
				<td><:$queue.mtime:></td>
				<td><:$queue.order:></td>
				<td><:$queue.priority:></td>
				<td><:$queue.flag:></td>
			</tr>
:}
		</table>
:}else{
		<div class="search_form">
			<form method="GET" action="/<:$screen_name:>/s">
				<input type="hidden" name="c" value="<:$MATCH[2]:>">
				けんさく&nbsp;<input type="text" size="40" name="grep" value="<:$GET.grep:>">
				普通<input type="radio" name="re" value="0"<:$GET.re ? "" : " checked":>>
				正規表現<input type="radio" name="re" value="1"<:$GET.re ? "checked" : "":>>
				<input type="submit" name="" value="発動">
:if $MATCH[2] == "s" {
				<br>
		<table>
			<tr>
				<td>ついっと</td>
				<td><input type="checkbox" name="c" value="t"<:match($GET.c,"t") ? " checked" : "":>></td>
				<td>@<:$screen_name:></td>
				<td><input type="checkbox" name="c" value="m"<:match($GET.c,"m") ? " checked" : "":>></td>
				<td></td>
				<td>じかん</td>
				<td>
					<select name="y">
						<option value="">*</option>
:for [2006..$SES.y] -> $i {
						<option value="<:$i:>"><:$i:></option>
:}
					</select>
					-
					<select name="m">
						<option value="">*</option>
:for [1..12] -> $i {
						<option value="<:$i:>"><:$i:></option>
:}
					</select>
					-
					<select name="d">
						<option value="">*</option>
:for [1..31] -> $i {
						<option value="<:$i:>"><:$i:></option>
:}
					</select>
				</td>
			</tr>
			<tr>
				<td>りついっと した</td>
				<td><input type="checkbox" name="c" value="r"<:match($GET.c,"r") ? " checked" : "":>></td>
				<td>りついっと された</td>
				<td><input type="checkbox" name="c" value="e"<:match($GET.c,"e") ? " checked" : "":>></td>
			</tr>
			<tr>
				<td>くおとついっと した</td>
				<td><input type="checkbox" name="c" value="q"<:match($GET.c,"q") ? " checked" : "":>></td>
				<td>くおとついっと した</td>
				<td><input type="checkbox" name="c" value="u"<:match($GET.c,"u") ? " checked" : "":>></td>
			</tr>
			<tr>
				<td><span style="color: yellow;">&#9733;</span> した</td>
				<td><input type="checkbox" name="c" value="f"<:match($GET.c,"f") ? " checked" : "":>></td>
				<td><span style="color: yellow;">&#9733;</span> された</td>
				<td><input type="checkbox" name="c" value="a"<:match($GET.c,"a") ? " checked" : "":>></td>
			</tr>
		</table>
:}
			</form>
		</div>
		<div class=""><:$rows:> 件
		</div>
:for $status -> $status {
		<div class="">
			<div class="timeline_name">
				<a href="https://twitter.com/#!/<:$status.user.screen_name:>" target="_blank"><span class="screen_name"><:$status.user.screen_name:></span></a>
				<span class="name"><:$status.user.name:></span>
				<span class="created_at"><:$status.created_at_formatted:></span>
				<a href="https://twitter.com/#!/<:$status.user.screen_name:>/status/<:$status.id:>" target="_blank"><span class="id">#<:$status.id:></span></a>
			</div>
			<div class="timeline_text"><:$status.text|mark_raw:></div>
		</div>
:}
:}
		<table>
			<tr>
:for [1..($rows / 48) + 1] -> $i {
:if $i != 1 && $i % 20 == 1 {
			</tr>
			<tr>
:}
				<td class="page"><a href="/<:$screen_name:>/<:$MATCH[2]:>/<:$i:>?<:$ENV.QUERY_STRING:>"><:$i:></a></td>
:}
			</tr>
		</table>
	</div>
</div>
</body>
</html>
EOF
}
