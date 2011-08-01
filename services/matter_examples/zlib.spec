# Entropy Matter, Automated Entropy Packages Build Service, example spec file

# List of packages required to be built.
# Comma separated, example: app-foo/bar, bar-baz/foo
# Mandatory, cannot be empty
packages: sys-libs/zlib

# Entropy repository where to commit packages
# Mandatory, cannot be empty
repository: community0

# Allow dependencies to be pulled in?
# Valid values are either "yes" or "no"
# Default is: no
dependencies: yes

# Allow package downgrade?
# Valid values are either "yes" or "no"
# Default is: no
downgrade: no

# Allow package rebuild?
# Valid values are either "yes" or "no"
# Default is: no
rebuild: yes

# Make possible to continue if one or more packages fail to build?
# Valid values are either "yes" or "no"
# Default is: no
keep-going: yes

# Allow new USE flags?
# Valid values are either "yes" or "no"
# Default is: no
new-useflags: no

# Allow removed USE flags?
# Valid values are either "yes" or "no"
# Default is: no
removed-useflags: yes

# Package pre execution script hook
# Valid value is path to executable file
# Env vars:
# BUILDER_PACKAGE_NAME       = name of the package that would be built
# pkgpre: /home/fabio/repos/entropy/services/matter_examples/pkgpre.sh

# Package build post execution script hook, executed for each package
# Valid value is path to executable file
# Env vars:
# BUILDER_PACKAGE_NAME       = name of the package that would be built
# pkgpost: /home/fabio/repos/entropy/services/matter_examples/pkgpost.sh

# For more info regarding exported environment variables, please see:
# matter --help