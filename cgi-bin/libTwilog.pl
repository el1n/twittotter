use 5.10.1;
use utf8;
use lib qw(/usr/local/lib/perl);
use vars qw($B $C);
use List::Util qw(first max maxstr min minstr reduce shuffle sum);
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

sub decode_TwilogTime
{
	my $DateTime = DateTime::Format::Strptime->new(pattern =>"%y%m%d %H%M%S")->parse_datetime(shift());
	$DateTime->subtract(seconds =>shift());
	return($DateTime);
}

sub encode_TwitterTime
{
	return(DateTime::Format::Strptime->new(pattern =>"%a %b %d %T +0000 %Y")->format_datetime(shift()));
}

sub parseTwilogXML
{
	my $file = shift();

	if(!-f $file){
		return();
	}elsif(!-s $file){
		return();
	}elsif(!(my $fh = Compress::Zlib::gzopen($file,"rb"))){
	}else{
		my $r;
		my $m;
		my $i;
		while($i = $fh->gzread($m,65536)){
			$r .= $m;
		}
		$fh->gzclose();

		if(!($r = XML::Simple::XMLin($r))){
			return();
		}

		my $user;
		if(!($user = $B->{Net::Twitter}->verify_credentials())){
			return();
		}
		delete($user->{status});

		map{
			$_ = {
				twilog =>$_,
				twitter =>{
					contributors =>undef,
					coordinates =>undef,
					created_at =>encode_TwitterTime(decode_TwilogTime($_->{time},$user->{utc_offset})),
					entities =>{
						hashtags =>[],
						media =>[],
						urls =>[],
						user_mentions =>[],
					},
					favorited =>0,
					geo =>undef,
					id =>$_->{id},
					id_str =>$_->{id},
					in_reply_to_screen_name =>undef,
					in_reply_to_status_id =>undef,
					in_reply_to_status_id_str =>undef,
					in_reply_to_user_id =>undef,
					in_reply_to_user_id_str =>undef,
					place =>undef,
					retweet_count =>0,
					retweeted =>0,
					retweeted_by =>[],
					retweeted_status =>{
						user =>{},
					},
					source =>"libTwilog.pl",
					text =>$_->{text},
					truncated =>0,
					user =>$user,
				},
			};
		}@{$r = [values(%{$r->{tweet}})]};
	}
}

1;
