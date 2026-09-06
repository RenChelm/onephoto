"""The Microsoft application (client) ID this build signs in with.

Set this once, before building the APK, and the people who install it never
see it: the first screen becomes a single "Sign in with Microsoft" button.

Get the value from the Azure portal -> App registrations -> your app ->
Overview -> "Application (client) ID".  The registration must use
"Accounts in any organizational directory and personal Microsoft accounts"
and have "Allow public client flows" turned on.  See README.md.

This is an identifier, not a credential -- public client apps have no secret,
so it is meant to ship inside the package.  Each person who installs the app
signs in with their own account and their token stays on their own device.

Leave it empty and the app falls back to asking for an ID on the sign-in
screen, which is handy while developing but is not what you want to ship.
"""

DEFAULT_CLIENT_ID = "13b76a7d-2f41-420c-bf38-c212814616c4"

# Overridden at runtime by the ONEPHOTO_CLIENT_ID environment variable, which
# is the convenient way to test a different registration on the desktop.
