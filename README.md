# FocusFinder
A small project aiming to move the focus system to a real application on Android and IOS (with a caveat).

# Coming Soon
- Focus on Android will save friend's timetables for more than one week. Internal discussions ongoing for how long to save for.
- NFC sharing Focus on Android
- Peer to Peer sharing to capture the latest timetables from friends easily this will not be in release 1.1.0 however will likely release before 1.2.0 

## FocusPy
A fully functional app running purely in Python. Comes with a fully functional installer script which handles updates smartly to ensure no data is lost. 

### Suported Operating Systems
* Windows - Fully working
* Fedora - Fully Working
* Debian - Fully Working
* Ubuntu - Fully Working
* Arch - Requires advanced knowledge for installation
* MAC OS - Untested



## Focus Finder on Android
An Android app to display your Focus timetable

It supports
* Fetching this weeks timetable data
* Sharing your timetable to your friends via a QR code or a friend.fff file
* Telling you whether you share any free periods with your friends
* Telling you the weather through a dedicated forecast tab
* Has a settings menu for enabling/disabling specific features and resetting data
* Showing which Busses are serviced by your bus stops, and departure times of any busses. 

It is written in Kotlin.

## Focus Finder on IOS
Work has begun on making the IOS app, but as an unverified developer it requires sideloading and renewing the certificate every 7 days.

Thus, using the IOS app for everyday users is not recommended. If you really want this app, then we recommend you purchase and android phone and join the superiors!!

It is written in Swift



## FocusKDE
A widget for KDE Plasma that allows users to quickly view their timetables whilst running a KDE plasma desktop environment. 

Won't be started until the completion of Focus Finder on Android.

## FocusFinderWatch
A port of Focus Finder on Android, with support for use on WearOS. Uses geckoview instead of webview, as webview isn't supported by WearOS to log into Focus.

The timetable UI is also changed from Focus on Android to be more watch friendly, and uses gestures as its only way of navigation.
