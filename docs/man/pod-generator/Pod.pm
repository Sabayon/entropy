use warnings;
use strict;
use 5.010;

# by Enlik
# April 2011

package Pod;

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
	
	print q{
=head1 NAME

B<equo> - Official Sabayon Linux Package Manager Client

=head1 SYNOPSIS

B<equo> [action] [basic_options] [options|extended_options] [atom | package_file | @set] ...

B<equo> [action] [basic_options] [options|extended_options] ...

B<equo> --info

B<equo> --help

B<equo> --version

=head1 DESCRIPTION

B<equo> is the definitive (rofl)... scratch it.
B<equo> is the official command-line interface to the Entropy framework. Primarily
used to ease packages management on Gentoo-based, Entropy-enabled distributions.

With B<equo> you can easily install and remove any application inside available and
enabled repositories: it's a binary package manager which brings the best from
apt, yum and rpm, keeping 100% backward Portage (see 'man emerge') compatibility.
Being Entropy a framework means that it's not just ended here.

For example, through B<equo> you can build your own software repository (called
Community Repository), do searches, keep your system secure, download packages'
source code, sanity check your system, see and be part of the User Generated
Content produced by other users.

};

	my $indent_lvl = 0;
	
	for my $h (@strs) {
		my ($indent, $cmd, $desc);
		$indent = $h->{indent};
		$cmd = $h->{command};
		$desc = $h->{desc};
		
		while ($indent_lvl > $indent) {
			print "\n=back\n\n";
			$indent_lvl--;
		}
		while ($indent_lvl < $indent) {
			print "\n=over\n\n";
			$indent_lvl++;
		}
		
		if ($indent == 0) {
			my $out;
			given($desc) {
				when (/Basic Options/) {
					$out = "BASIC_OPTIONS";
				}
				when (/Application Options/) {
					$out = "OPTIONS";
				}
				when(/Extended Options/) {
					$out = "EXTENDED_OPTIONS";
				}
				$out = uc($desc);
				$out =~ s/\s/_/g;
			}
			$desc = $out;
			print "=head1 ", $self->conv($desc), "\n";
		}
		else {
			if ($cmd) {
				my $out = "[$indent] B<" . $self->conv($cmd) . ">";
				print "=item ", $out, "\n";
			}
			
			print "\n", $self->conv($desc), "\n\n";
		}
	}
	
	print q{
=back

=head1 ENVIRONMENT

B<ETP_NOCACHE>=1: if set, all the Entropy framework will never use its internal
on-disk cache.


B<FORCE_EAPI>=N: if set to 1, 2 or 3 and used with 'B<equo> update', Entropy
repository synchronized will be force to use the provided EAPI to update
repositories.

B<ACCEPT_LICENSE>=license_id1:license_id2:...: this is a way to avoid equo
asking to accept specific licenses.

B<ETP_NO_COLOR>=1: disable entropy coloured output.

=head1 BUGS

Please report bugs to http://bugs.sabayonlinux.org.
B<equo> has a nice bug-reporting feature: whenever a valid exception occurs, it
asks the user to automatically submit the issue. B<WARNING>: to do efficient bug
squashing, some hardware specs are going to be collected, ask wrote before
submitting any data. No personal data is going to be uploaded and your report
will be kept private.

=head1 EXAMPLES

 work in progress

=head1 EXIT STATUS

B<equo> returns a zero exit status if the called command succeeded. Non zero is
returned in case of failure.

=head1 AUTHOR

Fabio Erculiani <lxnay@sabayon.org>

=head1 SEE ALSO

reagent(1), activator(1)
};
}

sub conv {
	my $self = shift;
	my $line = shift || return "";
	# $line =~ s/</E<lt>/g;
	# $line =~ s/>/E<gt>/g;

	my $c;
	my $o = "";
	for my $c (split //,$line) {
		if ($c eq "<")		{ $o .= "E<lt>" }
		elsif ($c eq ">")	{ $o .= "E<gt>" }
		else				{ $o .= $c }
	}
	$line = $o;
	
	$line =~ s/&/E<amp>/g;
	$line;
}

1;
