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
CLI_QE_0=SELECT * FROM `Queue` LEFT JOIN `Token` ON `Queue`.`screen_name` = `Token`.`screen_name` WHERE `Token`.`screen_name` = ? ORDER BY `Queue`.`priority`,`Queue`.`ctime` LIMIT 0,1
CLI_QE_1=UPDATE `Queue` SET `flag` = ?,`mtime` = CURRENT_TIMESTAMP WHERE `id` = ?
SALVAGE_0=SELECT ?,`status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` DESC LIMIT 0,1
SALVAGE_1=SELECT ?,`status_id` FROM `Tweet` WHERE `user_id` = ? AND `flag` & ? = ? ORDER BY `status_id` ASC LIMIT 0,1
SALVAGE_2=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_3=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referred_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
SALVAGE_4=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` DESC LIMIT 0,1
SALVAGE_5=SELECT ?,`Tweet`.`status_id` FROM `Tweet` LEFT JOIN `Bind` ON `Tweet`.`status_id` = `Bind`.`status_id` WHERE `Bind`.`referring_user_id` = ? AND `Bind`.`flag` & ? = ? ORDER BY `Tweet`.`status_id` ASC LIMIT 0,1
SALVAGE_6=INSERT `Tweet` (`status_id`,`user_id`,`screen_name`,`text`,`created_at`,`structure`,`flag`) VALUES (?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `structure` = VALUES(`structure`),`flag` = `flag` | ?
SALVAGE_7=SELECT COUNT(*) FROM `Bind` WHERE `status_id` = ? AND (`referring_user_id` = ? OR `referring_user_screen_name` = ?) AND (`referred_user_id` = ? OR `referred_user_screen_name` = ?) AND `flag` | ? = ?
SALVAGE_8=INSERT `Bind` (`status_id`,`referring_user_id`,`referring_user_screen_name`,`referred_user_id`,`referred_user_screen_name`,`flag`) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE `flag` = `flag` | ?
SALVAGE_9=SELECT * FROM `Tweet` WHERE `status_id` = ? LIMIT 0,1

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

		if($B->{DBT_CLI_QE_0}->execute("el1n") == 0){
			#return();
			exit(0);
		}
		my $r = $B->{DBT_CLI_QE_0}->fetchrow_hashref("",);

		local %SES;
		@SES{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)} = @{$r}{qw(user_id screen_name ACCESS_TOKEN ACCESS_TOKEN_SECRET)};

		&cb_prepare(
			[],
			[],
			[],
			{},
		);

print Data::Dumper::Dumper(my $r = $B->{Net::Twitter}->retweeted_of_me({id =>132426553,count =>200,max_id =>35584789427920896}));
print join("\n",sort(map{$_->{id}}@{$r}));
exit(0);

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
		die;
	}
	return();
}
