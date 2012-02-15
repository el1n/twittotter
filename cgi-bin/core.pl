#!/usr/bin/perl
use 5.10.1;
use utf8;
use lib qw(/usr/local/lib/perl);
use vars qw($B $C);
use List::Util qw(first max maxstr min minstr reduce shuffle sum);
use List::MoreUtils qw(uniq);
use Clone;
use Encode qw(encode decode);
use Compress::Zlib;
use Storable qw(thaw nfreeze);
use DBI;
use Cache::Memcached::libmemcached;
use XML::Simple;
use Config::Tiny;
use BlackCurtain::Ignorance;
use URI::Escape;
use DateTime;
use DateTime::Locale;
use DateTime::Format::DateParse;
use DateTime::Format::MySQL;
use Net::Twitter;
#use Net::Twitter::Lite;
use Calendar::Simple;
use BlackCurtain::Fragility;
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
use constant F_HASH =>1 << 19;
use constant F_REPLIED =>1 << 20;
use constant F_IMPORT_TWILOG =>1 << 33;
use constant F_SURELY_MASK =>F_TWEETS|F_REPLIES|F_FAVORITES|F_RETWEETED|F_TIMELINE;
use constant F_IMPORT_MASK =>F_SURELY_MASK|F_IMPORT_TWILOG;
use constant F_TYPE_MASK =>F_SURELY_MASK|F_RETWEETS|F_QUOTETWEETS|F_REPLYTO|F_QUOTETWEETED|F_FAVORITED;
use constant I_PRIORITY_LOW =>1;
use constant I_PRIORITY_MIDIUM =>2;
use constant I_PRIORITY_HIGH =>3;
require("libTwilog.pl");

BEGIN
{
	$C = Config::Tiny->read_string(<<'EOF');
TIMEZONE=Asia/Tokyo
LOCALE=ja_JP

HTML=/var/www/twittotter/html
TEMPLATE=/var/www/twittotter/html
CACHE_DIR=/tmp
CACHE_NAMESPACE=twittotter

LIMIT=48

[Cache]
DEFAULT_EXPIRE=600
PROFILE_EXPIRE=7200
STATIC_STATUS_EXPIRE=3600
STATUS_EXPIRE=1800
QUEUE_EXPIRE=1

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
METHOD_6=INSERT `Statistics` (`label`,`hash`) VALUES(?,SHA1(CONCAT_WS('/',?,DATE(CURRENT_TIMESTAMP)))) ON DUPLICATE KEY UPDATE `integer` = `integer` + 1
CLI_QC_0=TRUNCATE TABLE `Queue`
CLI_QI_0=SELECT * FROM `Queue` WHERE `user_id` = ? AND `order` LIKE ? AND `flag` & ? = ? LIMIT 0,1
CLI_QI_2=INSERT `Queue` (`user_id`,`screen_name`,`order`,`priority`,`atime`,`flag`) VALUES(?,?,?,?,DATE_ADD(CURRENT_TIMESTAMP,INTERVAL ? SECOND),?)
CLI_QE_0=SELECT * FROM `Queue` LEFT JOIN `Token` ON `Queue`.`user_id` = `Token`.`user_id` WHERE `atime` <= CURRENT_TIMESTAMP AND `flag` & 1 ORDER BY `Queue`.`priority` DESC,`Queue`.`ctime` ASC LIMIT 0,1
CLI_QE_1=UPDATE `Queue` SET `flag` = ?,`mtime` = CURRENT_TIMESTAMP WHERE `id` = ?
CLI_QE_2=UPDATE `Queue` SET `id` = LAST_INSERT_ID(`id`),`atime` = DATE_ADD(CURRENT_TIMESTAMP,INTERVAL 15 MINUTE) WHERE `atime` <= CURRENT_TIMESTAMP AND `flag` & 1 ORDER BY `priority` DESC,`ctime` ASC LIMIT 1
CLI_QE_3=SELECT * FROM `Queue` LEFT JOIN `Token` ON `Queue`.`user_id` = `Token`.`user_id` WHERE `Queue`.`id` = LAST_INSERT_ID()
CLI_R1_0=SELECT * FROM `Tweet` WHERE `revision` = 0 LIMIT 0,1
CLI_R2_0=SELECT * FROM `Tweet` LEFT JOIN `Token` ON `Tweet`.`user_id` = `Token`.`user_id` WHERE `Tweet`.`revision` = 1 LIMIT 0,1
CLI_R2_1=UPDATE `Tweet` SET `revision` = 2 WHERE `status_id` = ?
CLI_R2_2=UPDATE `Tweet` SET `structure` = ?,`revision` = 2 WHERE `status_id` = ?
CLI_R3_0=SELECT * FROM `Tweet` WHERE `revision` = 2 LIMIT 0,1
CLI_R3_1=UPDATE `Tweet` SET `text` = ?,`structure` = ?,`revision` = 3 WHERE `status_id` = ?
CLI_R4_0=SELECT * FROM `Tweet` WHERE `revision` = 3 ORDER BY `created_at` DESC LIMIT 0,1
CLI_R4_1=UPDATE `Tweet` SET `text` = ?,`structure` = ?,`revision` = 4 WHERE `status_id` = ?
CLI_R5_0=SELECT * FROM `Tweet` WHERE `revision` = 4 ORDER BY `created_at` DESC LIMIT 0,1
CLI_R5_1=UPDATE `Tweet` SET `text` = ?,`structure` = ?,`revision` = 5 WHERE `status_id` = ?
CLI_R5_2=UPDATE `Tweet` SET `revision` = 5 WHERE `status_id` = ?
CLI_R7_0=SELECT * FROM `Tweet` ORDER BY `created_at` DESC
CLI_SD_0=SELECT * FROM `Tweet` WHERE `status_id` = ? LIMIT 0,1

SALVAGE_0=SELECT ?,`status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` DESC LIMIT 0,1
SALVAGE_1=SELECT ?,`status_id` - 1 AS `status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` ASC LIMIT 0,1
SALVAGE_2=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_3=SELECT ?,`Tweet`.`status_id` - 1 AS `status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
SALVAGE_4=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_5=SELECT ?,`Tweet`.`status_id` - 1 AS `status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
#SALVAGE_6=INSERT `Tweet` (`status_id`,`user_id`,`screen_name`,`text`,`created_at`,`structure`,`flag`) VALUES (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `flag` = `flag` | ?
SALVAGE_7=SELECT 1 FROM `Bind` WHERE `status_id` = ? AND ((? IS NOT NULL AND `referring_user_id` = ?) OR (? IS NOT NULL AND `referring_screen_name` = ?)) AND ((? IS NOT NULL AND `referred_user_id` = ?) OR (? IS NOT NULL AND `referred_screen_name` = ?) OR (? IS NOT NULL AND `referred_hash` = ?)) AND `flag` & ? = ? LIMIT 0,1
SALVAGE_8=INSERT `Bind` (`status_id`,`referring_user_id`,`referring_screen_name`,`referred_user_id`,`referred_screen_name`,`referred_hash`,`flag`) VALUES(?,?,?,?,?,?,?)
SALVAGE_9=UPDATE `Bind` SET `flag` = ? WHERE `status_id` = ? AND ((? IS NOT NULL AND `referring_user_id` = ?) OR (? IS NOT NULL AND `referring_screen_name` = ?)) AND ((? IS NOT NULL AND `referred_user_id` = ?) OR (? IS NOT NULL AND `referred_screen_name` = ?) OR (? IS NOT NULL AND `referred_hash` = ?)) AND `flag` & ? = ?
SALVAGE_10=SELECT * FROM `Tweet` WHERE `status_id` = ? LIMIT 0,1
SALVAGE_11=INSERT `Tweet` (`status_id`,`user_id`,`screen_name`,`text`,`created_at`,`structure`,`flag`) VALUES (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `structure` = VALUES(`structure`),`flag` = `flag` | ?
SALVAGE_12=SELECT `flag` FROM `Tweet` WHERE `status_id` = ? LIMIT 0,1
SALVAGE_13=SELECT ?,`status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` DESC LIMIT 0,3
#SALVAGE_14=SELECT ?,`status_id` - 1 AS `status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` ASC LIMIT 0,1
ANALYZE_0=SELECT DATE_FORMAT(`created_at`,'%Y-%m') as `created_at_ym`,COUNT(*) as `i` FROM `Tweet` WHERE `user_id` = ? OR `screen_name` = ? GROUP BY `created_at_ym` ORDER BY `created_at_ym` DESC
ANALYZE_1=SELECT *,COUNT(*) as `i` FROM `Bind` WHERE (`referred_user_id` = ? OR `referred_screen_name` = ?) AND `flag` & ? = ? GROUP BY `referring_screen_name` ORDER BY `i` DESC
ANALYZE_2=SELECT *,COUNT(*) as `i` FROM `Bind` WHERE (`referring_user_id` = ? OR `referring_screen_name` = ?) AND `flag` & ? = ? GROUP BY `referred_screen_name` ORDER BY `i` DESC
ANALYZE_3=SELECT *,COUNT(*) as `i` FROM `Bind` WHERE (`referring_user_id` = ? OR `referring_screen_name` = ?) AND `referred_hash` IS NOT NULL GROUP BY `referred_hash` ORDER BY `i` DESC LIMIT 0,20

INDEX_0=INSERT `Token` (`user_id`,`screen_name`,`ACCESS_TOKEN`,`ACCESS_TOKEN_SECRET`,`ctime`) VALUES(?,?,?,?,CURRENT_TIMESTAMP) ON DUPLICATE KEY UPDATE `ACCESS_TOKEN` = ?,`ACCESS_TOKEN_SECRET` = ?
INDEX_1=SELECT DISTINCT `Tweet`.`status_id`,`Tweet`.`structure` FROM `Tweet` RIGHT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE (`Bind`.`referring_screen_name` = ? OR `Bind`.`referring_screen_name` = ?) AND `Bind`.`referred_hash` LIKE ? AND `Tweet`.`flag` & ? = ? AND `Tweet`.`flag` & ? = 0 ORDER BY `Tweet`.`created_at` DESC
SHOW_0=SELECT * FROM `Queue` WHERE `user_id` = ? OR `screen_name` = ? ORDER BY `ctime` DESC LIMIT 0,48
SHOW_1=SELECT COUNT(*) FROM `Queue` WHERE `user_id` = ? OR `screen_name` = ? ORDER BY `ctime` DESC LIMIT 0,48
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
#SEARCH_10_NP=YEAR(`Tweet`.`created_at`) >= ?
#SEARCH_11_NP=MONTH(`Tweet`.`created_at`) >= ?
#SEARCH_12_NP=DAY(`Tweet`.`created_at`) >= ?
#SEARCH_13_NP=YEAR(`Tweet`.`created_at`) <= ?
#SEARCH_14_NP=MONTH(`Tweet`.`created_at`) <= ?
#SEARCH_15_NP=DAY(`Tweet`.`created_at`) <= ?
SEARCH_16_NP=UNIX_TIMESTAMP(DATE(`Tweet`.`created_at`)) >= UNIX_TIMESTAMP(?)
SEARCH_17_NP=UNIX_TIMESTAMP(`Tweet`.`created_at`) >= UNIX_TIMESTAMP(?)
SEARCH_18_NP=UNIX_TIMESTAMP(DATE(`Tweet`.`created_at`)) < UNIX_TIMESTAMP(DATE_ADD(?,INTERVAL 1 YEAR))
SEARCH_19_NP=UNIX_TIMESTAMP(DATE(`Tweet`.`created_at`)) < UNIX_TIMESTAMP(DATE_ADD(?,INTERVAL 1 MONTH))
SEARCH_20_NP=UNIX_TIMESTAMP(DATE(`Tweet`.`created_at`)) < UNIX_TIMESTAMP(DATE_ADD(?,INTERVAL 1 DAY))
SEARCH_21_NP=(((`Bind`.`referring_user_id` = ? OR `Bind`.`referring_screen_name` = ?) AND (`Bind`.`referred_user_id` = ? OR `Bind`.`referred_screen_name` = ?)) AND `Bind`.`flag` & ? != 0)
SEARCH_22_NP=(((`Bind`.`referred_user_id` = ? OR `Bind`.`referred_screen_name` = ?) AND (`Bind`.`referring_user_id` = ? OR `Bind`.`referring_screen_name` = ?)) AND `Bind`.`flag` & ? != 0)

[Memcached]
HOST=127.0.0.1:11211

[QueueDescription]
SALVAGE.TIMELINE=過去のツイート取得 (200件)
SALVAGE.MENTION=過去のリプライ取得 (200件)
SALVAGE.RETWEETED=過去のリツイート取得 (200件)
SALVAGE.FAVORITE=過去のお気に入り取得 (200件)

EOF
	@{$C}{qw(Twitter API)} = @{Config::Tiny->read("core.conf")}{qw(Twitter API)};
	$B = {
		DBI =>DBI->connect(sprintf("dbi:mysql:database=%s;host=%s;port=%d",@{$C->{MySQL}}{qw(DATABASE HOST PORT)}),@{$C->{MySQL}}{qw(USERNAME PASSWORD),{mysql_enable_utf8 =>1}}),
		Cache::Memcached =>Cache::Memcached::libmemcached->new({servers =>[split(/ /o,$C->{Memcached}->{HOST})]}),
		BlackCurtain::Fragility =>BlackCurtain::Fragility->new(requests_redirectable =>[]),
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

sub pack_structure
{
	my $g = shift() // $_;

	$g->{structure} = gzip($g->{structure});
	return($g);
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

sub figures
{
	my($label) = @_;

	$B->{DBT_METHOD_6}->execute($label,$label);

	return();
}

if(defined($ENV{GATEWAY_INTERFACE})){
	BlackCurtain::Ignorance->new(
		[
			[qr/./,undef,\&cb_prepare],
			[qr/^\/?$/,undef,\&cb_index],
			[qr/^(\/([0-9A-Za-z_]{1,15}))\/c\/?$/,undef,\&cb_conf],
			[qr/^(\/([0-9A-Za-z_]{1,15})(?:\.([abd-z]+))?(?:\/([a-z]+))?(?:\/\@([0-9A-Za-z_]{1,15}))?(?:\/(?:(\d{4})(?:\-(\d{1,2})(?:\-(\d{1,2}))?)?)?(\-)?(?:(\d{4})(?:\-(\d{1,2})(?:\-(\d{1,2}))?)?)?)?)(?:\/(\d+))?\/?$/,16,\&cb_show],
			[qr/./,undef,sub{$SES{HTTP_REFERER} = $ENV{REQUEST_URI}}],
		],
		CGI::Session =>["driver:memcached",undef,{Memcached =>$B->{Cache::Memcached}}],
		Text::Xslate =>[
			path =>[split(/ /o,$C->{_}->{TEMPLATE})],
			cache =>1,
			cache_dir =>$C->{_}->{CACHE_DIR},
			function =>{
				#omit =>sub{ return(length($_[0]) > $_[1] ? substr($_[0],0,$_[1])."..." : $_[0]) },
				omit =>sub{ my($g,$i) = (Encode::decode_utf8(shift()),shift());return(length($g) > $i ? substr($g,0,$i)."..." : $g) },
			},
			module =>[
				Text::Xslate::Bridge::Star,
				URI::Escape,
				Calendar::Simple,
			],
		],
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
				#&new_queue($user_id,$screen_name,"UPDATE.TIMELINE.ALL",I_PRIORITY_LOW,0,F_TIMELINE);
				#&new_queue($user_id,$screen_name,"COMPARE.TIMELINE",I_PRIORITY_HIGH,0,F_TWEETS);
				#&new_queue($user_id,$screen_name,"COMPARE.MENTION",I_PRIORITY_HIGH,0,F_REPLIES);
				#&new_queue($user_id,$screen_name,"COMPARE.RETWEETED",I_PRIORITY_HIGH,0,F_RETWEETED);
				#&new_queue($user_id,$screen_name,"COMPARE.FAVORITE",I_PRIORITY_HIGH,0,F_FAVORITES);
				#&new_queue($user_id,$screen_name,"NULL.TEST",I_PRIORITY_HIGH,0,0);
				&new_queue($user_id,$screen_name,"ANALYZE",I_PRIORITY_LOW,0,0);
			}
			return($user_id);
		}

		printf("%s() : %d\n",$_,&ini_queue(@ARGV));
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

		if($B->{DBT_CLI_QE_2}->execute() == 0){
			#return();
			exit(0);
		}
		if($B->{DBT_CLI_QE_3}->execute() == 0){
			#return();
			exit(1);
		}
		my $r = $B->{DBT_CLI_QE_3}->fetchrow_hashref();

		#&mod_queue($r->{id},($r->{flag} & ~F_STATE) | F_PROCESS);

		local %SES;
		@SES{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)} = @{$r}{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)};

		my $i = -1;
		if(!&cb_prepare(
			[],
			[],
			{regular =>1},
		)){
			die();
		}
		given($r->{order}){
			when(/^NULL/o){
			}
			when(/^UPDATE/o){
				$i = &salvage(
					[$r->{screen_name}],
					[undef,$r->{screen_name}],
					{
						user_id =>$r->{user_id},
						flag =>$r->{flag} & F_IMPORT_MASK,
						axis =>1,
					},
				);

				@{$r}{qw(priority atime)} = (I_PRIORITY_LOW,1800);
				&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
				&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
			}
			when(/^SALVAGE/o){
				$i = &salvage(
					[$r->{screen_name}],
					[undef,$r->{screen_name}],
					{
						user_id =>$r->{user_id},
						flag =>$r->{flag} & F_IMPORT_MASK,
						axis =>-1,
					},
				);

				if($i > 0){
					@{$r}{qw(priority atime)} = (I_PRIORITY_MIDIUM,1200);
					&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
					&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
				}elsif($i == 0){
					&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
				}else{
					@{$r}{qw(priority atime)} = (I_PRIORITY_MIDIUM,600);
					&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
					&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
				}
			}
			when(/^COMPARE/o){
				$i = &salvage(
					[$r->{screen_name}],
					[undef,$r->{screen_name}],
					{
						user_id =>$r->{user_id},
						flag =>$r->{flag} & F_IMPORT_MASK,
						axis =>-1,
					},
				);

				if($i > 0){
					@{$r}{qw(priority atime)} = (I_PRIORITY_MIDIUM,600);
					&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
					&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
				}elsif($i == 0){
					&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
				}else{
					@{$r}{qw(priority atime)} = (I_PRIORITY_MIDIUM,600);
					&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
					&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
				}
			}
			when(/^IMPORT\.TWILOG/o){
				if(my $status = &parseTwilogXML($r->{screen_name}.".xml.gz")){
					$i = &salvage(
						[$r->{screen_name}],
						[undef,$r->{screen_name}],
						{
							user_id =>$r->{user_id},
							flag =>$r->{flag} & F_IMPORT_MASK,
							axis =>1,
							status =>$status,
						},
					);
	
					if($i > 0){
						&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
					}elsif($i == 0){
						&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
					}else{
						@{$r}{qw(priority atime)} = (I_PRIORITY_HIGH,1800);
						&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
						&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
					}
				}
			}
			when(/^ANALYZE/o){
				$i = &analyze(
					[$r->{screen_name}],
					[undef,$r->{screen_name}],
					{
						user_id =>$r->{user_id},
					},
				);

				@{$r}{qw(priority atime)} = (I_PRIORITY_LOW,3600);
				&mod_queue($r->{id},($r->{flag} & ~F_STATE) | ($i >= 0 ? F_FINISH : F_FAILURE));
				&new_queue(@{$r}{qw(user_id screen_name order priority atime flag)});
			}
			default{
				die();
			}
		}
		printf("[Queue#%d %s] %s's queue, returned %d.\n",@{$r}{qw(id order screen_name)},$i);
	}
	when("-sd"){
		if($B->{DBT_CLI_SD_0}->execute(shift(@ARGV)) == 0){
			#return();
			die();
		}
		print Data::Dumper::Dumper(unpack_structure($B->{DBT_CLI_SD_0}->fetchrow_hashref()));
	}
	when("-u2"){
		while($B->{DBT_CLI_R2_0}->execute() != 0){
			my $r = unpack_structure($B->{DBT_CLI_R2_0}->fetchrow_hashref());
			if(($r->{flag} & F_RETWEETED) && $#{$r->{twitter}->{structure}->{retweeted_by}} == -1){
				local %SES;
				@SES{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)} = @{$r}{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)};
				if(!&cb_prepare(
					[],
					[],
					{regular =>1},
				)){
					die();
				}

				if(!&r2_processer(@{$r}{qw(structure flag)})){
					die(join(":",$r->{status_id},$@));
				}
				pack_structure($r);
				if($B->{DBT_CLI_R2_2}->execute(@{$r}{qw(structure status_id)}) == 0){
					die;
				}
				printf("Converted %d, revision %d to 2, \$#retweeted_by = %d\n",@{$r}{qw(status_id revision)},$#{$r->{twitter}->{structure}->{retweeted_by}});
			}else{
				if($B->{DBT_CLI_R2_1}->execute(@{$r}{qw(status_id)}) == 0){
					die;
				}
				printf("Converted %d, revision %d to 2.\n",@{$r}{qw(status_id revision)});
			}
		}
	}
	when("-u3"){
		while($B->{DBT_CLI_R3_0}->execute() != 0){
			my $r = unpack_structure($B->{DBT_CLI_R3_0}->fetchrow_hashref());

			if(!&r3_processer(@{$r}{qw(structure flag)})){
				die($r->{status_id});
			}
			pack_structure($r);
			if($B->{DBT_CLI_R3_1}->execute(@{$r}{qw(text structure status_id)}) == 0){
				die($r->{status_id});
			}
			printf("Converted %d, revision %d to 3.\n",@{$r}{qw(status_id revision)});
		}
	}
	when("-u4"){
		while($B->{DBT_CLI_R4_0}->execute() != 0){
			my $r = unpack_structure($B->{DBT_CLI_R4_0}->fetchrow_hashref());

			if(!&r3_processer(@{$r}{qw(structure flag)})){
				die($r->{status_id});
			}
			if(!&r4_processer(@{$r}{qw(structure flag)})){
				die($r->{status_id});
			}
			pack_structure($r);
			if($B->{DBT_CLI_R4_1}->execute(@{$r}{qw(text structure status_id)}) == 0){
				die($r->{status_id});
			}
			printf("Converted %d, revision %d to 4.\n",@{$r}{qw(status_id revision)});
		}
	}
	when("-u5"){
		while($B->{DBT_CLI_R5_0}->execute() != 0){
			my $r = unpack_structure($B->{DBT_CLI_R5_0}->fetchrow_hashref());

			if(my @urls = grep{!defined($_->{expanded_url})}(@{$r->{structure}->{twitter}->{entities}->{urls}},@{$r->{structure}->{twitter}->{entities}->{media}})){
				for(@urls){
					printf("Need expand %s.\n",$_);
				}
				if(!&r3_processer(@{$r}{qw(structure flag)})){
					die($r->{status_id});
				}
				pack_structure($r);
				if($B->{DBT_CLI_R5_1}->execute(@{$r}{qw(text structure status_id)}) == 0){
					die($r->{status_id});
				}
				printf("Converted %d, revision %d to 5.\n",@{$r}{qw(status_id revision)});
			}else{
				if($B->{DBT_CLI_R5_2}->execute(@{$r}{qw(status_id)}) == 0){
					die($r->{status_id});
				}
				printf("Skip %d, revision %d to 5.\n",@{$r}{qw(status_id revision)});
			}
		}
	}
	when("-u7"){
		if($B->{DBT_CLI_R7_0}->execute() != 0){
			while(my $r = unpack_structure($B->{DBT_CLI_R7_0}->fetchrow_hashref())){
				if(!&r7_processer(@{$r}{qw(structure flag)})){
					die($r->{status_id});
				}
				printf("Converted %d.\n",@{$r}{qw(status_id)});
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
		my $referred_hash = $#_ > 0 ? shift() : undef;
		my $flag = shift();

		if($B->{DBT_SALVAGE_7}->execute(
			$status_id,
			$referring_user_id,
			$referring_user_id,
			$referring_screen_name,
			$referring_screen_name,
			$referred_user_id,
			$referred_user_id,
			$referred_screen_name,
			$referred_screen_name,
			$referred_hash,
			$referred_hash,
			$flag & F_TYPE_MASK,
			$flag & F_TYPE_MASK,
		) > 0){
			if($B->{DBT_SALVAGE_9}->execute(
				$flag,
				$status_id,
				$referring_user_id,
				$referring_user_id,
				$referring_screen_name,
				$referring_screen_name,
				$referred_user_id,
				$referred_user_id,
				$referred_screen_name,
				$referred_screen_name,
				$referred_hash,
				$referred_hash,
				$flag & F_TYPE_MASK,
				$flag & F_TYPE_MASK,
			) == 0){
				return();
			}
		}else{
			if($B->{DBT_SALVAGE_8}->execute(
				$status_id,
				$referring_user_id,
				$referring_screen_name,
				$referred_user_id,
				$referred_screen_name,
				$referred_hash,
				$flag,
			) == 0){
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
		given($flag & F_SURELY_MASK){
			when(F_TWEETS){
				$i = $axis ? 0 : 1;
			}
			when(F_REPLIES){
				$i = $axis ? 2 : 3;
			}
			when(F_RETWEETED){
				$i = $axis ? 13 : 1;
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
		return(@{$B->{DBT_SALVAGE_.$i}->fetchall_arrayref()->[-1]});
	}

	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name) = @{$q};
	my($location,$screen_name,$issue) = @{$m};
	my($user_id,$flag,$axis) = @{$d}{qw(user_id flag axis)};
	$user_id //= user_id($screen_name);
	$flag = $flag | F_SYNCHRONIZED;

	my $r = [];
	given($flag & F_IMPORT_MASK){
		when(F_TWEETS){
			my $status;
			my $i = 1;
			do{
				if(!($status = $B->{Net::Twitter}->user_timeline({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,page =>$i,include_entities =>1,include_rts =>1}))){
					warn();
					return(-1);
				}
				push(@{$r},@{$status});
				++$i;
			}while($axis >= 0 && $#{$status} == 199);
		}
		when(F_REPLIES){
			my $status;
			my $i = 1;
			do{
				if(!($status = $B->{Net::Twitter}->mentions({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,page =>$i,include_entities =>1,include_rts =>1}))){
					warn();
					return(-1);
				}
				push(@{$r},@{$status});
				++$i;
			}while($axis >= 0 && $#{$status} == 199);
		}
		when(F_RETWEETED){
			my $status;
			my $i = 1;
			do{
				if(!($status = $B->{Net::Twitter}->retweets_of_me({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,page =>$i,include_entities =>1,include_rts =>1}))){
					warn();
					return(-1);
				}
				push(@{$r},@{$status});
				++$i;
			}while($axis >= 0 && $#{$status} == 199);
		}
		when(F_FAVORITES){
			my $status;
			my $i = 1;
			do{
				if(!($status = $B->{Net::Twitter}->favorites({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,page =>$i,include_entities =>1,include_rts =>1}))){
					warn();
					return(-1);
				}
				push(@{$r},@{$status});
				++$i;
			}while($axis >= 0 && $#{$status} == 199);
		}
		when(F_TIMELINE){
			my $status;
			my $i = 1;
			do{
				if(!($status = $B->{Net::Twitter}->friends_timeline({id =>$user_id,&edge($user_id,$flag,$axis),count =>200,page =>$i,include_entities =>1,include_rts =>1}))){
					warn();
					return(-1);
				}
				push(@{$r},@{$status});
				++$i;
			}while($axis >= 0 && $#{$status} == 199);
		}
		when(F_TWEETS | F_IMPORT_TWILOG){
			$r = $d->{status};
		}
		default{
			warn("Unknown flag.");
			return(-1);
		}
	}
	if($axis >= 0){
		$r = [reverse(@{$r})];
	}

	for my $structure (@{$r}){
		$structure->{retweeted_by} = [];
		my $flag = $flag & F_SURELY_MASK && $structure->{user}->{id} eq $user_id ? $flag | F_REGULAR : $flag;
		my @flag;

		given($flag & F_SURELY_MASK){
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
				for my $i (1..16){
					my $r;
					if(!($r = $B->{Net::Twitter}->retweeted_by({id =>$structure->{id},count =>100,page =>$i,include_entities =>1}))){
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

		$structure = {twitter =>$structure};
		#if(!&r1_processer($structure,$flag)){
		#	return(-1);
		#}
		#if(!&r2_processer($structure,$flag)){
		#	return(-1);
		#}
		if(!&r3_processer($structure,$flag)){
			warn("r3_processer error.");
			return(-1);
		}
		if(!&r4_processer($structure,$flag)){
			warn("r4_processer error.");
			return(-1);
		}
		#if(!&r5_processer($structure,$flag)){
		#	return(-1);
		#}
		#if(!&r6_processer($structure,$flag)){
		#	return(-1);
		#}
		if(!&r7_processer($structure,$flag)){
			warn("r7_processer error.");
			return(-1);
		}

		for(@flag){
			$flag |= $_;
		}

		if($B->{DBT_SALVAGE_10}->execute($structure->{twitter}->{id}) > 0){
			my $structure_store = unpack_structure($B->{DBT_SALVAGE_10}->fetchrow_hashref())->{structure};
			my $structure_clone = Clone::clone($structure);
	
			if($structure_store->{twitter}->{id} != $structure->{twitter}->{id}){
				warn();
				return(-1);
			}

			if($flag & F_REGULAR){
				$structure = $structure_clone;
				warn(sprintf("[STATUS#%d] based clone.",$structure->{twitter}->{id}));
			}else{
				$structure = $structure_store;
				warn(sprintf("[STATUS#%d] based store.",$structure->{twitter}->{id}));
			}
			if($flag & F_RETWEETED){
				$structure->{twitter}->{retweeted_by} = $structure_clone->{twitter}->{retweeted_by};
				warn(sprintf("[STATUS#%d] F_RETWEETED.",$structure->{twitter}->{id}));
			}else{
				$structure->{twitter}->{retweeted_by} = $structure_store->{twitter}->{retweeted_by};
				warn(sprintf("[STATUS#%d] F_RETWEETED.",$structure->{twitter}->{id}));
			}
			if($flag & F_IMPORT_TWILOG){
				$structure->{twilog} = $structure_clone->{twilog};
			}elsif(defined($structure_store->{twilog})){
				$structure->{twilog} = $structure_store->{twilog};
			}
		}
		if($B->{DBT_SALVAGE_11}->execute(
			$structure->{twitter}->{id},
			$structure->{twitter}->{user}->{id},
			$structure->{twitter}->{user}->{screen_name},
			$structure->{twittotter}->{text_deployed},
			encode_MySQLTime($structure->{twitter}->{created_at}),
			gzip($structure),
			$flag,
			$flag,
		) == 0){
			warn(sprintf("MySQL DBT_SALVAGE_11 error."));
			return(-1);
		}
	}

	return($#{$r} + 1);
}

sub r1_processer
{
	my $structure = shift();
	my $flag = shift();

	return(1);
}

sub r2_processer
{
	my $structure = shift();
	my $flag = shift();

	$structure = $structure->{twitter};

	for my $i (1..16){
		my $r;
		if(!($r = $B->{Net::Twitter}->retweeted_by({id =>$structure->{id},count =>100,page =>$i,include_entities =>1}))){
			return();
		}
		if(ref($r) && $#{$r} != -1){
			for(@{$r}){
				&bind(
					$structure->{id},
					$_->{id},
					$_->{screen_name},
					$structure->{user}->{id},
					$structure->{user}->{screen_name},
					F_REGULAR | F_RETWEETED | F_SYNCHRONIZED,
				);
			}
			push(@{$structure->{retweeted_by}},@{$r});
		}else{
			last();
		}
	}

	return(1);
}

sub r3_processer
{
	my $structure = shift();
	my $flag = shift();

	if($structure->{twitter}->{retweeted_status}->{user}->{id} != 0){
		$structure->{twittotter} = {
			text =>sprintf("RT \@%s: %s",$structure->{twitter}->{retweeted_status}->{user}->{screen_name},$structure->{twitter}->{retweeted_status}->{text}),
			entities =>Clone::clone($structure->{twitter}->{retweeted_status}->{entities}),
		};
	}else{
		$structure->{twittotter} = {
			text =>$structure->{twitter}->{text},
			entities =>Clone::clone($structure->{twitter}->{entities}),
		};
	}
	$structure->{twittotter}->{text_deployed} = $structure->{twittotter}->{text};
	$structure->{twitpic} = [];
	$structure->{yfrog} = [];
	$structure->{flickr} = [];
	$structure->{youtube} = [];

	for(@{$structure->{twittotter}->{entities}->{urls}},@{$structure->{twittotter}->{entities}->{media}}){
		$_->{expanded_url} //= $_->{url} =~ /^[a-z]+:\/\//o ? $_->{url} : "http://".$_->{url};

		my($code,undef,undef,undef) = $B->{BlackCurtain::Fragility}->spider($_->{expanded_url},"none");
		if($B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/bgm-fes\.jp\//io){
			# http://bgm-fes.jp/
			# 正常なHTMLを常に HTTP/1.1 503 Service Unavailable で応答してくる糞サイト、死ぬべき
			$code = -1;
		}elsif($B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/www\.toranoana\.jp\//io){
			# http://www.toranoana.jp/*
			# 年齢認証で403を返す、アホ？
			$code = -1;
		}elsif($B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/lockerz.com\//io){
			# http://lockerz.com/*
			# すぐ500吐くゴミ鯖
			$code = -1;
		}elsif($B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/hatsukari\.2ch\.at\//io){
			# http://hatsukari.2ch.at/*
			# 常に500のゴミ鯖、だがLWP/UAのConnection Timeoutでは？
			$code = -1;
		}elsif($B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/ux\.nu\//io){
			# http://ux.nu/*
			# URL短縮サービスが死んでどうすんだアホ
			$code = -1;
		}elsif($code == 500 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/\/112.78.197.156\//io){
			# http:///112.78.197.156/*
			# http://volac.net/aup/img/の404からLocation: http:///112.78.197.156/aflink/link.cgi?page=a404で302のクズ、"/"が3つある
			$code = -2;
		}elsif($code == 403 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/www\.robotentertainment\.com\/games\/orcsmustdie/io){
			# http://www.robotentertainment.com/games/orcsmustdie
			# Fragility側の問題による403
			$code = -1;
		}elsif($code == 502 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/am6\.jp\//io){
			# http://am6.jp/*
			# 非携帯端末からのアクセスを拒否している？
			$code = -1;
		}elsif($code == 403 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/www\.pfsense\.com\/packages\/config\//io){
			# http://www.pfsense.com/packages/config/
			# pfsenseのパッケージは別のところに移動している
			$code = -1;
		}elsif($code == 403 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/en\.expreview\.com\//io){
			# http://en.expreview.com/*
			# Fragility側の問題による403
			$code = -1;
		}elsif($code == 403 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/twitter.com\/.+?\/photo\//io){
			# 非公開アカウントの画像は常に403
			$code = -1;
		}elsif($code == 403 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/www\.youtube\.com\/watch/io){
			# 削除された動画は常に403
			$code = -1;
		}elsif($code == 403 && $B->{BlackCurtain::Fragility}->{s}->request()->uri() =~ /^http:\/\/d\.hatena\.ne\.jp\//io){
			# プライベートモードによる403
			$code = -1;
		}
		if($code == 200){
			$_->{expanded_url} = ${$B->{BlackCurtain::Fragility}->{s}->request()->uri()};
			$structure->{twittotter}->{text_deployed} =~s/\Q$_->{url}\E/$_->{expanded_url}/g;
		}elsif($code == 401){
			$_->{expanded_url} = ${$B->{BlackCurtain::Fragility}->{s}->request()->uri()};
			$structure->{twittotter}->{text_deployed} =~s/\Q$_->{url}\E/$_->{expanded_url}/g;
			warn("Failed spider ".$_->{expanded_url}." -> ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}elsif($code == 404){
			$_->{expanded_url} = ${$B->{BlackCurtain::Fragility}->{s}->request()->uri()};
			$structure->{twittotter}->{text_deployed} =~s/\Q$_->{url}\E/$_->{expanded_url}/g;
			warn("Failed spider ".$_->{expanded_url}." -> ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}elsif($code == 410){
			$_->{expanded_url} = ${$B->{BlackCurtain::Fragility}->{s}->request()->uri()};
			$structure->{twittotter}->{text_deployed} =~s/\Q$_->{url}\E/$_->{expanded_url}/g;
			warn("Failed spider ".$_->{expanded_url}." -> ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}elsif($code == 500 && $B->{BlackCurtain::Fragility}->{s}->{_msg} =~ /connect: Connection timed out/io){
			$_->{expanded_url} = ${$B->{BlackCurtain::Fragility}->{s}->request()->uri()};
			$structure->{twittotter}->{text_deployed} =~s/\Q$_->{url}\E/$_->{expanded_url}/g;
			warn("Failed spider ".$_->{expanded_url}." -> ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code.", Bullshit server.");
		}elsif($code == -1){
			$_->{expanded_url} = ${$B->{BlackCurtain::Fragility}->{s}->request()->uri()};
			$structure->{twittotter}->{text_deployed} =~s/\Q$_->{url}\E/$_->{expanded_url}/g;
			warn("Failed spider ".$_->{expanded_url}." -> ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}elsif($code == -2){
			#$_->{expanded_url} = ${$B->{BlackCurtain::Fragility}->{s}->request()->uri()};
			$structure->{twittotter}->{text_deployed} =~s/\Q$_->{url}\E/$_->{expanded_url}/g;
			warn("Failed spider ".$_->{expanded_url}." -> ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}else{
			warn("Failed spider ".$_->{expanded_url}." -> ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
			return();
		}
	}

	for($structure->{twittotter}->{text_deployed} =~m/(?<![^ ])#(\w+)(?![^ ])/o){
		&bind(
			$structure->{twitter}->{id},
			$structure->{twitter}->{user}->{id},
			$structure->{twitter}->{user}->{screen_name},
			undef,
			undef,
			$_,
			$flag | F_HASH,
		);
	}

	for($structure->{twittotter}->{text_deployed} =~m/http:\/\/twitpic\.com\/([0-9A-Za-z_]+)/io){
		my $id = $1;
		my($code,undef,$r,undef) = eval{$B->{BlackCurtain::Fragility}->spider(sprintf("http://api.twitpic.com/2/media/show.xml?id=%s",$id),"xml")};
		if($@){
			warn($@);
			($code,$r,undef,undef) = $B->{BlackCurtain::Fragility}->spider(sprintf("http://api.twitpic.com/2/media/show.xml?id=%s",$id),"none");
			$r =~s/<message>.*?<\/message>/<message><\/message>/igo;
			$r = XML::Simple::XMLin($r);
		}
		if($code == 200){
			push(@{$structure->{twitpic}},$r);
		}elsif($code == 404){
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}else{
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
			return();
		}
	}
	for($structure->{twittotter}->{text_deployed} =~m/http:\/\/yfrog\.com\/([0-9A-Za-z_]+)/io){
		my($code,undef,$r,undef) = $B->{BlackCurtain::Fragility}->spider(sprintf("http://yfrog.com/api/xmlInfo?path=%s",$1),"xml");
		if($code == 200){
			push(@{$structure->{yfrog}},$r);
		}elsif($code == 404){
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}else{
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
			return();
		}
	}
	for($structure->{twittotter}->{text_deployed} =~m/http:\/\/www.flickr.com\/photos\/[^\/]+?\/([0-9A-Za-z_]+)/io){
		my($code,undef,$r,undef) = $B->{BlackCurtain::Fragility}->spider(sprintf("http://api.flickr.com/services/rest?method=flickr.photos.getInfo&api_key=%s&secret=%s&photo_id=%s",$C->{API}->{FLICKR_KEY},$C->{API}->{FLICKR_SECRET},$1),"xml");
		if($code == 200){
			push(@{$structure->{flickr}},$r);
		}elsif($code == 404){
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}else{
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
			return();
		}
	}
	for($structure->{twittotter}->{text_deployed} =~m/http:\/\/www\.youtube\.com\/watch\?v=([0-9A-Za-z_-]+)/io){
		my($code,undef,$r,undef) = $B->{BlackCurtain::Fragility}->spider(sprintf("http://gdata.youtube.com/feeds/api/videos/%s",$1),"xml");
		if($code == 200){
			push(@{$structure->{youtube}},$r);
		}elsif($code == 400){
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}elsif($code == 403){
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}elsif($code == 404){
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
		}else{
			warn("Failed spider ".$B->{BlackCurtain::Fragility}->{s}->request()->uri().", returned ".$code);
			return();
		}
	}

	return(1);
}

sub r4_processer
{
	my $structure = shift();
	my $flag = shift();

	$structure = $structure->{twitter};

	my %b;
	$structure->{retweeted_by} = [grep{$b{$_->{id}}++ == 0}@{$structure->{retweeted_by}}];

	return(1);
}

sub r5_processer
{
	my $structure = shift();
	my $flag = shift();

	return(1);
}

sub r6_processer
{
	my $structure = shift();
	my $flag = shift();

	return(1);
}

sub r7_processer
{
	my $structure = shift()->{twitter};
	my $flag = shift();

	if(defined($structure->{in_reply_to_status_id})){
		&bind(
			$structure->{in_reply_to_status_id},
			$structure->{user}->{id},
			$structure->{user}->{screen_name},
			$structure->{in_reply_to_user_id},
			$structure->{in_reply_to_screen_name},
			F_REPLIED | F_SYNCHRONIZED,
		);
		warn(sprintf("%s -> %s Binded F_REPLIED(%d).",@{$structure}{qw(id in_reply_to_status_id)},F_REPLIED));
	}

	return(1);
}

sub analyze
{
	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name) = @{$q};
	my($location,$screen_name,$issue) = @{$m};
	my($user_id,$flag,$axis) = @{$d}{qw(user_id flag axis)};
	$user_id //= user_id($screen_name);

	#if($B->{DBT_ANALYZE_0}->execute($user_id,$screen_name)){
	#	$r->{"archives"} = $B->{DBT_ANALYZE_0}->fetchall_arrayref({});
	#}
	if($B->{DBT_ANALYZE_1}->execute($user_id,$screen_name,F_REPLIES,F_REPLIES)){
		$r->{"result_".F_REPLIES} = $B->{DBT_ANALYZE_1}->fetchall_arrayref({});
	}
	if($B->{DBT_ANALYZE_2}->execute($user_id,$screen_name,F_REPLYTO,F_REPLYTO)){
		$r->{"result_".F_REPLYTO} = $B->{DBT_ANALYZE_2}->fetchall_arrayref({});
	}
	$r->{"result_".(F_REPLIES|F_REPLYTO)} = [sort{
		$b->{"i_".(F_REPLIES|F_REPLYTO)} <=> $a->{"i_".(F_REPLIES|F_REPLYTO)}
	}map{
		my $t = {};
		$t->{id} = undef;
		$t->{screen_name} = $_;
		$t->{"i_".F_REPLIES} = ((grep{$_->{referring_screen_name} eq $t->{screen_name}}@{$r->{"result_".F_REPLIES}})[0] // {i =>0})->{i};
		$t->{"i_".F_REPLYTO} = ((grep{$_->{referred_screen_name} eq $t->{screen_name}}@{$r->{"result_".F_REPLYTO}})[0] // {i =>0})->{i};
		$t->{"i_".(F_REPLIES|F_REPLYTO)} = $r->{"i_".F_REPLIES} + $r->{"i_".F_REPLYTO};
		$t
	}grep{defined($_)}uniq(map{$_->{referring_screen_name}}@{$r->{"result_".F_REPLIES}},map{$_->{referred_screen_name}}@{$r->{"result_".F_REPLYTO}})];

	if($B->{DBT_ANALYZE_3}->execute($user_id,$screen_name)){
		$r->{"result_hash"} = $B->{DBT_ANALYZE_3}->fetchall_arrayref({});
	}

	my $sign = join(".",$C->{_}->{CACHE_NAMESPACE},$screen_name).".";
	$B->{Cache::Memcached}->set($sign."analyze",$r,$C->{Cache}->{PROFILE_EXPIRE});

	return(1);
}

sub cb_prepare
{
	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($location,$screen_name,$issue) = @{$m};

	if(defined($ENV{GATEWAY_INTERFACE})){
		figures("pv");
		if(!$SES{access}++){
			figures("uu");
		}
	}

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
			#access_token =>$C->{Twitter}->{ACCESS_TOKEN},
			#access_token_secret =>$C->{Twitter}->{ACCESS_TOKEN_SECRET},
			max_retries =>2,
		);
	}
	if($d->{regular} && !$B->{Net::Twitter}->verify_credentials()){
		die("verify_credentials() is failed. [".$SES{screen_name}."#".$SES{user_id}."]");
	}
	return(1);
}

sub cb_index
{
	if(!defined($GET{op})){
		my $r;
		my $sign = join(".",$C->{_}->{CACHE_NAMESPACE},$GET{l});
		if(!defined($r = $B->{Cache::Memcached}->get($sign))){
			$r = {
				id =>undef,
				name =>"ついっとったー",
				profile_background_color =>"C0DEED",
				profile_image_url =>"/img/twittotter.png",
				profile_image_url_https =>"/img/twittotter.png",
				profile_link_color =>"0084B4",
				profile_sidebar_border_color =>"C0DEED",
				profile_sidebar_fill_color =>"DDEEF6",
				profile_text_color =>"'333333'",
				screen_name =>undef,
				status =>[],
			};
			if($GET{l} =~ /^(info|history)$/io){
				my $hash = {
					info =>"twittotter%",
					history =>"twittotter_history",
				}->{$GET{l}};
				if($B->{DBT_INDEX_1}->execute(qw(el1n xmms),$hash,F_REGULAR | F_TWEETS,F_REGULAR | F_TWEETS,F_RETWEETS) == 0){
				}
				map{$_ = prepare_structure($_)}@{$r->{status} = $B->{DBT_INDEX_1}->fetchall_arrayref({})};
				$B->{Cache::Memcached}->set($sign,$r,$C->{Cache}->{DEFAULT_EXPIRE});
			}
		}

		return("Text::Xslate",$r // {},file =>"core.Xslate");
	}elsif($GET{op} eq "login" && $GET{oauth_token} && $GET{oauth_verifier}){
		$B->{Net::Twitter}->request_token($SES{REQUEST_TOKEN});
		$B->{Net::Twitter}->request_token_secret($SES{REQUEST_TOKEN_SECRET});
		@SES{qw(ACCESS_TOKEN ACCESS_TOKEN_SECRET user_id screen_name)} = $B->{Net::Twitter}->request_access_token(token =>$GET{oauth_token},verifier =>$GET{oauth_verifier});
		if($SES{user_id} > 0){
			if($B->{DBT_INDEX_0}->execute(@SES{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET ACCESS_TOKEN ACCESS_TOKEN_SECRET)}) == 0){
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
	}elsif($GET{op} eq "login" && $SES{user_id}){
		return("jump","http://".$ENV{HTTP_HOST}.$ENV{SCRIPT_NAME}."/".$SES{screen_name});
	}elsif($GET{op} eq "login"){
		my $r = $B->{Net::Twitter}->get_authorization_url(callback =>"http://".$ENV{HTTP_HOST}.$ENV{SCRIPT_NAME}."/?op=login");
		$SES{REQUEST_TOKEN} = $B->{Net::Twitter}->request_token();
		$SES{REQUEST_TOKEN_SECRET} = $B->{Net::Twitter}->request_token_secret();

		return("jump",$r);
	}elsif($GET{op} eq "logout"){
		map{$SES{$_} = undef}grep(!/^_/o,keys(%SES));

		return("jump","http://".$ENV{HTTP_HOST}.$ENV{SCRIPT_NAME}."/");
	}else{
	}
	return("raw","unknown op");
}

sub cb_conf
{
	my $q = shift();
	my $m = shift();
	my $d = shift();
	my $g = shift();
	my($screen_name) = @{$m};

	if($GET{v} > 0){
		$SES{v} ^= 1 << ($GET{v} - 1)
	}

	return("jump",$ENV{HTTP_REFERER} // $SES{HTTP_REFERER} // "/");
}

sub cb_show
{
	my $q = shift();
	my $m = shift();
	$m->[3] .= $GET{c};
	$m->[3] ||= "t";
	$m->[5] //= $GET{"y-"};
	$m->[6] //= $GET{"m-"};
	$m->[7] //= $GET{"d-"};
	$m->[9] //= defined($m->[8]) ? undef : $GET{"-y"} || $m->[5];
	$m->[10] //= defined($m->[8]) ? undef : $GET{"-m"} || $m->[6];
	$m->[11] //= defined($m->[8]) ? undef : $GET{"-d"} || $m->[7];
	$m->[8] //= $m->[3] =~ /s/o ? "-" : undef;
	$m->[12] = $m->[12] < 1 ? 0 : $m->[12] - 1;
	my $d = shift();
	my $g = shift();
	my($location,$screen_name,$issue,$clause,@g) = @{$m};
	my $user_id = user_id($screen_name);
	#$clause .= $GET{c};

	my $time = time();
	my @time = localtime($time);
	%BORROW = (
		IS_SHOW =>1,
		IS_STATIC =>length($clause) == 1 && $clause =~ /^[jotmnrequfa]$/o && !defined($GET{grep}) && !defined($GET{egrep}) && !defined($g[0]) && !defined($g[1]) && !defined($g[4]) && !defined($g[5]) && $g[8] == 0 ? 1 : 0,
		IS_SEARCH =>length($clause) == 1 && $clause =~ /^[jotmnrequfa]$/o && !defined($GET{grep}) && !defined($GET{egrep}) && !defined($g[0]) && !defined($g[1]) ? 0 : 1,

		location =>$location,
		u =>$time,
		s =>$time[0],
		n =>$time[1],
		h =>$time[2],
		d =>$time[3],
		m =>$time[4] + 1,
		y =>$time[5] + 1900,
		w =>$time[6],
		cal =>{
			m =>$m->[10] // $GET{"m-"} // ($m->[9] ? 12 : $time[4] + 1),
			y =>$m->[9] // $GET{"y-"} // $time[5] + 1900,
		},
	);

	my $sign = join(".",$C->{_}->{CACHE_NAMESPACE},$screen_name).".";
	my $r;
	if(!defined($r = $B->{Cache::Memcached}->get($sign."profile"))){
		if(!($r = $B->{Net::Twitter}->show_user({screen_name =>$screen_name}))){
			return(&cb_exception(undef,undef,undef,"ユーザ情報取得失敗"));
		}

		if($B->{DBT_ANALYZE_0}->execute($user_id,$screen_name)){
			$r->{"archives"} = $B->{DBT_ANALYZE_0}->fetchall_arrayref({});
		}

		$B->{Cache::Memcached}->set($sign."profile",$r,$C->{Cache}->{PROFILE_EXPIRE});
	}

	sub prepare_structure
	{
		my $g = unpack_structure(shift());
		my $structure = $g->{structure}->{twitter};
		$structure->{text} = $g->{structure}->{twittotter}->{text};
		$structure->{entities} = $g->{structure}->{twittotter}->{entities};

		for(@{$structure->{entities}->{media}},@{$structure->{entities}->{urls}}){
			if(defined($_->{expanded_url})){
				if($_->{expanded_url} =~ /^http:\/\/twitpic\.com\/([0-9A-Za-z_]+)$/io){
					my @g = @{(grep{$_->{short_id} == $1}@{$g->{structure}->{twitpic}})[0] // {}}{qw(id type)};
					if($g[0]){
						$_->{media_url} = sprintf("http://s1-01.twitpicproxy.com/photos/full/%s.%s",@g);
						$_->{thumb_url} = sprintf("http://s1-01.twitpicproxy.com/photos/thumb/%s.%s",@g);
						push(@{$structure->{entities}->{media}},$_);
					}
				}elsif($_->{expanded_url} =~ /^(http:\/\/yfrog\.com\/[0-9A-Za-z_]+)$/io){
					my @g = @{(grep{$_->{links}->{yfrog_link} == $1}@{$g->{structure}->{yfrog}})[0]->{links} // {}}{qw(image_link yfrog_thumb)};
					$_->{media_url} = shift(@g);
					$_->{thumb_url} = shift(@g);
					push(@{$structure->{entities}->{media}},$_);
				}elsif($_->{expanded_url} =~ /^(http:\/\/www\.flickr\.com\/photos\/.+?)$/io){
					my @g = @{(grep{$_->{photo}->{urls}->{url}->{content} == $1}@{$g->{structure}->{flickr}})[0]->{photo} // {}}{qw(farm server id secret)};
					$_->{media_url} = sprintf("http://farm%s.staticflickr.com/%s/%s_%s_b.jpg",@g);
					$_->{thumb_url} = sprintf("http://farm%s.staticflickr.com/%s/%s_%s_t.jpg",@g);
					push(@{$structure->{entities}->{media}},$_);
				}elsif(defined($_->{media_url_https})){
					$_->{media_url} = $_->{media_url_https};
					$_->{thumb_url} = $_->{media_url_https};
				}
				if(defined($_->{media_url})){
					#$structure->{text} =~s/$_->{url}/$_->{expanded_url}/g;
					$structure->{text} =~s/$_->{url}/<a href="$_->{expanded_url}" target="_blank">$_->{expanded_url}<\/a>&nbsp;<a href="$_->{media_url}" target="_blank">&raquo;<\/a>/g;
				}else{
					#$structure->{text} =~s/$_->{url}/$_->{expanded_url}/g;
					$structure->{text} =~s/$_->{url}/<a href="$_->{expanded_url}" target="_blank">$_->{expanded_url}<\/a>/g;
				}
			}else{
				$structure->{text} =~s/$_->{url}/<a href="$_->{url}" target="_blank">$_->{url}<\/a>/g;
			}
		}

		#$structure->{text} =~s/((?:ht|f)tps?:\/{2}[^\/]+\/[\x21-\x7E]+)/<a href="$1" target="_blank">$1<\/a>/g;
		#$structure->{text} =~s/(?<![^ ])(#\w+)(?![^ ])/<a href="https:\/\/twitter.com\/#!\/search\/$1" target="_blank">$1<\/a>/g;
		$structure->{text} =~s/(?<![^ ])(#\w+)(?![^ ])/"<a href=\"https:\/\/twitter.com\/#!\/search\/".uri_escape_utf8($1)."\" target=\"_blank\">$1<\/a>"/eg;

		if(defined($structure->{retweeted_status}->{id})){
			$structure->{text} =~s/^RT \@([0-9A-Za-z_]{1,15}):/RT <a href="https:\/\/twitter.com\/#!\/$1" target="_blank">\@$1<\/a>&nbsp;<a href="https:\/\/twitter.com\/#!\/$1\/status\/$structure->{retweeted_status}->{id}" target="_blank">&raquo;<\/a>:/g;
		}elsif(defined($structure->{in_reply_to_status_id})){
			$structure->{text} =~s/^\@([0-9A-Za-z_]{1,15})/<a href="https:\/\/twitter.com\/#!\/$1" target="_blank">\@$1<\/a>&nbsp;<a href="https:\/\/twitter.com\/#!\/$1\/status\/$structure->{in_reply_to_status_id}" target="_blank">&raquo;<\/a>/g;
		}else{
		}
			$structure->{text} =~s/\@([0-9A-Za-z_]{1,15})(?![^<>]+>)(?![^<>]+<\/a>)/<a href="https:\/\/twitter.com\/#!\/$1" target="_blank">\@$1<\/a>/g;

		my $dt = encode_DateTime($structure->{created_at});
		$structure->{created_at_formatted} = $dt->strftime("%Y-%m-%d %H:%M");
		$structure->{created_at_splited} = {
			u =>$dt->epoch(),
			s =>$dt->second(),
			n =>$dt->minute(),
			h =>$dt->hour(),
			d =>$dt->day(),
			m =>$dt->month(),
			y =>$dt->year(),
			w =>$dt->day_of_week(),
		};

		return($structure);
	}

	if($r->{protected} && $SES{id} != $r->{id}){
	}elsif($clause eq "o"){
		if(!defined($r->{twittotter}->{analyze} = $B->{Cache::Memcached}->get($sign."analyze"))){
			$r->{twittotter}->{message} = "";
		}
	}elsif($clause eq "j"){
		if(!defined($r->{queue} = $B->{Cache::Memcached}->get($sign.$clause))){
			if(!$B->{DBT_SHOW_0}->execute($user_id,$screen_name)){
			}
			map{
1;
			}@{$r->{queue} = $B->{DBT_SHOW_0}->fetchall_arrayref({})};
			$B->{DBT_SEARCH_0}->execute();
			push(@{$r->{queue}},($B->{DBT_SEARCH_0}->fetchrow_array())[0]);
			$B->{Cache::Memcached}->set($sign.$clause,$r->{queue},$C->{Cache}->{QUEUE_EXPIRE});
		}
	}elsif(!$BORROW{IS_STATIC} || !defined($r->{status} = $B->{Cache::Memcached}->get($sign.$clause))){
		my @where_time;
		my @where_base;
		my @where_char;
		my @bind;

		if($g[1] > 0){
			if(defined($g[4])){
				push(@where_time,$C->{MySQL}->{SEARCH_17_NP});
				push(@bind,join("-",$g[1],$g[2] || 1,$g[3] || 1));
			}else{
				for my $i (1..3){
					if($g[$i] > 0){
						push(@where_time,$C->{MySQL}->{SEARCH_.(6 + $i)._NP});
						push(@bind,$g[$i]);
					}
				}
			}
		}
		if($g[5] > 0){
			if(defined($g[4])){
				if(defined($g[7])){
					push(@where_time,$C->{MySQL}->{SEARCH_20_NP});
					push(@bind,join("-",$g[5],$g[6] || 1,$g[7] || 1));
				}elsif(defined($g[6])){
					push(@where_time,$C->{MySQL}->{SEARCH_19_NP});
					push(@bind,join("-",$g[5],$g[6] || 1,$g[7] || 1));
				}else{
					push(@where_time,$C->{MySQL}->{SEARCH_18_NP});
					push(@bind,join("-",$g[5],$g[6] || 1,$g[7] || 1));
				}
			}
		}
		for(qw(t m n r e q u f a i)){
			if($clause =~ /$_/){
				my($i,$index,$flag) = @{{
					t =>[1,[0,1],F_TWEETS],
					m =>[3,[0,1,4,5],F_REPLIES],
					n =>[2,[0,1,4,5],F_REPLYTO],
					r =>[2,[0,1,4,5],F_RETWEETS],
					e =>[3,[0,1,4,5],F_RETWEETED],
					q =>[2,[0,1,4,5],F_QUOTETWEETS],
					u =>[3,[0,1,4,5],F_QUOTETWEETED],
					f =>[2,[0,1,4,5],F_FAVORITES],
					a =>[3,[0,1,4,5],F_FAVORITES],
					i =>[2,[0,1,4,5],F_TIMELINE],
					t_ =>[1,[0,1],F_TWEETS],
					m_ =>[22,[0,1,2,3,4],F_REPLIES|F_REPLIED],
					n_ =>[21,[0,1,2,3,4],F_REPLYTO|F_REPLIED],
					r_ =>[2,[0,1,4,5],F_RETWEETS],
					e_ =>[3,[0,1,4,5],F_RETWEETED],
					q_ =>[2,[0,1,4,5],F_QUOTETWEETS],
					u_ =>[3,[0,1,4,5],F_QUOTETWEETED],
					f_ =>[2,[0,1,4,5],F_FAVORITES],
					a_ =>[3,[0,1,4,5],F_FAVORITES],
					i_ =>[2,[0,1,4,5],F_TIMELINE],
				}->{defined($g[0]) ? $_."_" : $_}};

				push(@where_base,$C->{MySQL}->{SEARCH_.$i._NP});
				push(@bind,($user_id,$screen_name,0,$g[0],$flag,$flag)[@{$index}]);
			}
		}
		if($GET{e} == 1 && (length($GET{egrep}) || length($GET{grep}))){
			push(@where_char,$C->{MySQL}->{SEARCH_6_NP});
			push(@bind,$GET{egrep} // $GET{grep});
		}elsif($GET{e} == 0 && (length($GET{grep}))){
			for(split(/\s+/o,$GET{grep})){
				push(@where_char,$C->{MySQL}->{SEARCH_5_NP});
				push(@bind,"%".$_."%");
			}
		}
		if($GET{o} =~ /URLONLY/io){
			push(@where_char,$C->{MySQL}->{SEARCH_6_NP});
			push(@bind,q/http:\/\//);
		}elsif($GET{o} =~ /IMGONLY/io){
			push(@where_char,$C->{MySQL}->{SEARCH_6_NP});
			push(@bind,q/(\\.(bmp|gif|jpe?g|png)|http:\/\/(twitpic|yfrog.com|www.flickr.com|twitter.com\/[^[:space:]]+\/photo\/))/);
		}elsif($GET{o} =~ /MOVONLY/io){
			push(@where_char,$C->{MySQL}->{SEARCH_6_NP});
			push(@bind,q/(http:\/\/(www.youtube.com|www.ustream.tv|(www|live).nicovideo.jp))/);
		}

		my @embed = (
			$#where_time != -1 ? join(" AND ",@where_time) : 1,
			$#where_base != -1 ? join(" OR ",@where_base) : 0,
			$#where_char != -1 ? join(" AND ",@where_char) : 1,
			$g[8] * $C->{_}->{LIMIT},
			$C->{_}->{LIMIT},
		);

		my $query = $C->{MySQL}->{SEARCH_0_NP};
		for(@embed){
			$query =~s/{}/$_/o;
		}
		map{$_ = prepare_structure($_)}@{$r->{status} = $B->{DBI}->selectall_arrayref($query,{Slice =>{}},@bind)};
		$B->{DBT_SEARCH_0}->execute();
		push(@{$r->{status}},($B->{DBT_SEARCH_0}->fetchrow_array())[0]);

		if($BORROW{IS_STATIC} && $#{$r->{status}} > 0){
			$B->{Cache::Memcached}->set($sign.$clause,$r->{status},$C->{Cache}->{STATIC_STATUS_EXPIRE});
		}
	}
	if(ref($r->{status}) eq "ARRAY"){
		$r->{rows} = pop(@{$r->{status}});
	}elsif(ref($r->{queue}) eq "ARRAY"){
		$r->{rows} = pop(@{$r->{queue}});
	}else{
		$r->{rows} = 0;
	}

	return($issue ? $issue : "Text::Xslate",$r // {},file =>"core.Xslate");
}
