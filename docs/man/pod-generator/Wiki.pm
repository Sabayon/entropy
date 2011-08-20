use warnings;
use strict;
use 5.010;

# by Enlik
# April 2011

package Wiki;

sub new {
	my $class = shift;
	my $strs = shift || die "specify parameter";
	
	unless (ref $strs eq "ARRAY") {
		die "wrong parameter";
	}
	
	my $self = {
		strs => $strs
	};
	
	bless $self, $class;
}

sub generate {
	my $self = shift;
	my @strs = @{$self->{strs}};
	
	for my $h (@strs) {
		my ($indent, $cmd, $desc);
		$indent = $h->{indent};
		$cmd = $h->{command};
		$desc = $h->{desc};
		
		# only one space on the beginning of commands
		# (format requires a space)
		if ($indent == 1) {
			print " ";
		}
		elsif ($indent >= 2) {
			print " "x(8*$indent-8);
		}
		
		if ($indent == 0) {
			print "\n===$desc===\n\n";
		}
		else {
			print "'''",$cmd,"'''", " "x8, $desc, "\n";
		}
	}
}

1;
