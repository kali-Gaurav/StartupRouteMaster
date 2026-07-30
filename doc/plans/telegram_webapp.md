 Twitter
Home
FAQ
Apps
API
Protocol
Schema
Recent changes
Designing Mini Apps
Implementing Mini Apps
Initializing Mini Apps
ThemeParams
StoryShareParams
StoryWidgetLink
ScanQrPopupParams
PopupParams
PopupButton
EmojiStatusParams
DownloadFileParams
SafeAreaInset
ContentSafeAreaInset
BackButton
BottomButton
SettingsButton
HapticFeedback
CloudStorage
BiometricManager
BiometricRequestAccessParams
BiometricAuthenticateParams
Accelerometer
AccelerometerStartParams
DeviceOrientation
DeviceOrientationStartParams
Gyroscope
GyroscopeStartParams
LocationManager
LocationData
DeviceStorage
SecureStorage
WebAppInitData
WebAppUser
WebAppChat
Validating data received via the Mini App
Validating data for Third-Party Use
Events Available for Mini Apps
Adding Bots to the Attachment Menu
Additional Data in User-Agent
Testing Mini Apps
BotsTelegram Mini Apps
Telegram Mini Apps
With Mini Apps developers can use JavaScript to create infinitely flexible interfaces that can be launched right inside Telegram — and can completely replace any website.

Like bots, Mini Apps support seamless authorization, payments via third-party payment providers (with Google Pay and Apple Pay out of the box), delivering tailored push notifications to users, and much more.

To see a Mini App in action, try our sample @DurgerKingBot.

Recent changes
April 3, 2026
Added the method requestChat to the class WebApp.
March 1, 2026
Bot API 9.5

Added the field iconCustomEmojiId to the class BottomButton.
July 3, 2025
Bot API 9.1

Added the method hideKeyboard to the class WebApp.
April 11, 2025
Bot API 9.0

Added the field DeviceStorage, allowing Mini Apps to use persistent local storage on the user's device.
Added the field SecureStorage, allowing Mini Apps to use a secure local storage on the user's device for sensitive data.
November 17, 2024
Bot API 8.0

This is the largest update in the history of Telegram mini apps – adding more than 10 new features and monetization options for developers. To read more about all these changes, check out this dedicated blog post.

Full-screen Mode

Mini Apps are now able to become full-screen in both portrait and landscape mode – allowing them to host more games, play widescreen media and support immersive user experiences.
Added the methods requestFullscreen and exitFullscreen to toggle full-screen mode.
Added the fields safeAreaInset and contentSafeAreaInset, allowing Mini Apps to ensure that their content properly respects the device's safe area margins.
Further added the fields isActive and isFullscreen to the class WebApp.
Added the events activated, deactivated, safeAreaChanged, contentSafeAreaChanged, fullscreenChanged and fullscreenFailed.
Homescreen Shortcuts

Mini Apps can now be accessed via direct shortcuts added to the home screen of mobile devices.
Added the method addToHomeScreen to create a shortcut for users to add to their home screens.
Added the method checkHomeScreenStatus to determine the status and support of the home screen shortcut for the Mini App on the current device.
Added the events homeScreenAdded and homeScreenChecked.
Emoji Status

Mini Apps can now prompt users to set their emoji status – or request access to later sync it automatically with in-game badges, third-party APIs and more.
Added the method setEmojiStatus to let users manually confirm a custom emoji as their new status via a native dialog.
Added the method requestEmojiStatusAccess for obtaining permission to later update a user's emoji status via the Bot API method setUserEmojiStatus.
Added the events emojiStatusSet, emojiStatusFailed and emojiStatusAccessRequested.
Media Sharing and File Downloads

Users can now share media directly from Mini Apps – sending referral codes, custom memes, artwork and more to any chat or posting them as a story.
Added the method shareMessage to share media from Mini Apps to Telegram chats. Also see PreparedInlineMessage.
Added the method downloadFile, introducing support for a native popup that prompts users to download files from the Mini App.
Added the events shareMessageSent, shareMessageFailed and fileDownloadRequested.
Geolocation Access

Mini Apps can now request geolocation access to users, allowing them to build virtually any location-based service, from games with dynamic points of interest to interactive maps for events.
Added the field LocationManager to the class WebApp.
Added the events locationManagerUpdated and locationRequested.
Device Motion Tracking

Mini Apps can now track detailed device motion data, allowing them to implement better productivity tools, immersive VR experiences and more.
Added the fields isOrientationLocked, Accelerometer, DeviceOrientation and Gyroscope to the class WebApp.
Added the methods lockOrientation and unlockOrientation to control the screen orientation.
Added the events accelerometerStarted, accelerometerStopped, accelerometerChanged, accelerometerFailed, deviceOrientationStarted, deviceOrientationStopped, deviceOrientationChanged, deviceOrientationFailed, gyroscopeStarted, gyroscopeStopped, gyroscopeChanged, gyroscopeFailed.
Subscription Plans and Gifts for Telegram Stars

Mini Apps now support paid subscriptions powered by Telegram Stars – monetizing their efforts with multiple tiers of content and features.
Mini Apps can use their balance of Telegram Stars to send gifts to their users.
You can read more on implementing Paid Subscriptions and Gifts in our Bot API documentation.
Loading Screen Customization

Mini Apps can customize their loading screen, adding their own icon and specific colors for light and dark themes.
You can access these customization settings in @BotFather via /mybots > Select Bot > Bot Settings > Configure Mini App > Enable Mini App
Hardware-specific Optimizations

Mini Apps running on Android can now receive basic information about a device's processing hardware, allowing them to optimize user experience based on the device's capabilities.
This information includes the OS, App and SDK's respective versions as well as the device's model and performance class.
General

The field photo_url in the class WebAppUser is now available to all Mini Apps, allowing them to access a user's profile photo if their privacy settings allow for it.
Third parties (e.g., Mini App builders, external SDKs etc.) that receive or process data on behalf of Mini Apps are now able to validate it without knowing the App's bot token.
Debugging options have been expanded to include full support for iOS devices. You can use these tools to find app-specific issues in your Mini App.
September 6, 2024
Bot API 7.10

Added the field SecondaryButton to the class WebApp.
Added the event secondaryButtonClicked.
Renamed the class MainButton to the class BottomButton.
Added the field bottomBarColor and the method setBottomBarColor to the class WebApp.
Added the field bottom_bar_bg_color to the class ThemeParams.
July 31, 2024
Bot API 7.8

Added the option for bots to set a Main Mini App, which can be previewed and launched directly from a button in the bot's profile or a link.
Added the method shareToStory to the class WebApp.
July 7, 2024
Bot API 7.7

Added the field isVerticalSwipesEnabled and the methods enableVerticalSwipes, disableVerticalSwipes to the class WebApp.
Added the event scanQrPopupClosed.
July 1, 2024
Bot API 7.6

Added the field section_separator_color to the class ThemeParams.
Changed the default opening mode for Direct Link Mini Apps.
March 31, 2024
Bot API 7.2

Added the field BiometricManager to the class WebApp.
December 29, 2023
Bot API 7.0

Added the field SettingsButton to the class WebApp.
Added the fields header_bg_color, accent_text_color, section_bg_color, section_header_text_color, subtitle_text_color, destructive_text_color to the class ThemeParams.
Mini Apps no longer close when the method WebApp.openTelegramLink is called.
September 22, 2023
Bot API 6.9

Added the field CloudStorage to the class WebApp.
Added the methods requestWriteAccess and requestContact to the class WebApp.
Added the fields added_to_attachment_menu and allows_write_to_pm to the class WebAppUser.
Added the events writeAccessRequested and contactRequested.
Added the ability to set any header color using the setHeaderColor method.
April 21, 2023
Bot API 6.7

Added support for launching Mini Apps from inline query results and from a direct link.
Added the method switchInlineQuery to the class WebApp.
December 30, 2022
Bot API 6.4

Added the field platform, the optional parameter options to the method openLink and the methods showScanQrPopup, closeScanQrPopup, readTextFromClipboard to the class WebApp.
Added the events qrTextReceived, clipboardTextReceived.
August 12, 2022
Bot API 6.2

Added the field isClosingConfirmationEnabled and the methods enableClosingConfirmation, disableClosingConfirmation, showPopup, showAlert, showConfirm to the class WebApp.
Added the field is_premium to the class WebAppUser.
Added the event popupClosed.
June 20, 2022
Bot API 6.1

Added the ability to use bots added to the attachment menu in group, supergroup and channel chats.
Added support for t.me links that can be used to select the chat in which the attachment menu with the bot will be opened.
Added the fields version, headerColor, backgroundColor, BackButton, HapticFeedback and the methods isVersionAtLeast, setHeaderColor, setBackgroundColor, openLink, openTelegramLink, openInvoice to the class WebApp.
Added the field secondary_bg_color to the class ThemeParams.
Added the method offClick to the class MainButton.
Added the fields chat, can_send_after to the class WebAppInitData.
Added the events backButtonClicked, settingsButtonClicked, invoiceClosed.
Designing Mini Apps
Color Schemes
Mini Apps always receive data about the user's current color theme in real time, so you can adjust the appearance of your interfaces to match it. For example, when users switch between Day and Night modes or use various custom themes.

Jump to technical information

Design Guidelines
Telegram apps are known for being snappy, smooth and following a consistent cross-platform design. Your Mini App should ideally reflect these principles.

All elements should be responsive and designed with a mobile-first approach.
Interactive elements should mimic the style, behavior, and intent of UI components that already exist.
All included animations should be smooth, ideally 60fps.
All inputs and images should contain labels for accessibility purposes.
The app should deliver a seamless experience by monitoring the dynamic theme-based colors provided by the API and using them accordingly.
Ensure that the app’s interface respects the safe area and content safe area to avoid overlapping with control elements, especially when using fullscreen mode.
For Android devices, consider the additional information in the User-Agent (see User-Agent details) and adjust for the device’s performance class, minimizing animations and visual effects on low-performance devices to ensure smooth performance.
Implementing Mini Apps
Telegram currently supports seven different ways of launching Mini Apps: the main Mini App from a profile button, from a keyboard button, from an inline button, from the bot menu button, via inline mode, from a direct link – and even from the attachment menu.

Types of buttons
Keyboard Button Mini Apps
TL;DR: Mini Apps launched from a web_app type keyboard button can send data back to the bot in a service message using Telegram.WebApp.sendData. This makes it possible for the bot to produce a response without communicating with any external servers.

Users can interact with bots using custom keyboards, buttons under bot messages, as well as by sending freeform text messages or any of the attachment types supported by Telegram: photos and videos, files, locations, contacts and polls. For even more flexibility, bots can utilize the full power of HTML5 to create user-friendly input interfaces.

You can send a web_app type KeyboardButton that opens a Mini App from the specified URL.

To transmit data from the user back to the bot, the Mini App can call the Telegram.WebApp.sendData method. Data will be transmitted to the bot as a String in a service message. The bot can continue communicating with the user after receiving it.

Good for:

Сustom data input interfaces (a personalized calendar for selecting dates; selecting data from a list with advanced search options; a randomizer that lets the user “spin a wheel” and chooses one of the available options, etc.)
Reusable components that do not depend on a particular bot.
Inline Button Mini Apps
TL;DR: For more interactive Mini Apps like @DurgerKingBot, use a web_app type Inline KeyboardButton, which gets basic user information and can be used to send a message on behalf of the user to the chat with the bot.

If receiving text data alone is insufficient or you need a more advanced and personalized interface, you can open a Mini App using a web_app type Inline KeyboardButton.

From the button, a Mini App will open with the URL specified in the button. In addition to the user's theme settings, it will receive basic user information (ID, name, username, language_code) and a unique identifier for the session, query_id, which allows messages on behalf of the user to be sent back to the bot.

The bot can call the Bot API method answerWebAppQuery to send an inline message from the user back to the bot and close the Mini App. After receiving the message, the bot can continue communicating with the user.

Good for:

Fully-fledged web services and integrations of any kind.
The use cases are effectively unlimited.
Launching Mini Apps from the Menu Button
TL;DR: Mini Apps can be launched from a customized menu button. This simply offers a quicker way to access the app and is otherwise identical to launching a mini app from an inline button.

By default, chats with bots always show a convenient menu button that provides quick access to all listed commands. With Bot API 6.0, this button can be used to launch a Mini App instead.

To configure the menu button, you must specify the text it should show and the Mini App URL. There are two ways to set these parameters:

To customize the button for all users, use @BotFather (the /setmenubutton command or Bot Settings > Menu Button).
To customize the button for both all users and specific users, use the setChatMenuButton method in the Bot API. For example, change the button text according to the user's language, or show links to different Mini Apps based on a user's settings in your bot.
Apart from this, Mini Apps opened via the menu button work in the exact same way as when using inline buttons.

@DurgerKingBot allows launching its Mini App both from an inline button and from the menu button.

Launching the main Mini App
TL;DR: If your bot is a mini app, you can add a prominent Launch app button as well as high-quality demo videos and screenshots to the bot’s profile. To do this, go to @BotFather and set up your bot's Main Mini App.

If your bot is a mini app, you can unlock a number of features that streamline and simplify the way in which users view and interact with it. To do this, go to @BotFather and set up your bot's Main Mini App.

After setting a main mini app, you'll be able to upload detailed media preview demos to publicly highlight your app's key features on its profile. A Launch app button will also appear, allowing users to open your app directly from its profile. Bots that enabled a main mini app will be displayed in the Apps tab of the search for users who have launched them.

Media previews support multiple languages – so you can upload translated versions of your previews that will be shown to users based on their app language.

A bot's main Mini App can also be opened in the current chat by direct link in the format https://t.me/botusername?startapp. If a non-empty startapp parameter is included in the link, it will be passed to the Mini App in the start_param field and in the GET parameter tgWebAppStartParam.

Examples

https://t.me/botusername?startapp
https://t.me/botusername?startapp=command
https://t.me/botusername?startapp=command&mode=compact

In this mode, Mini Apps can use the chat_type and chat_instance parameters to keep track of the current chat context. This introduces support for concurrent and shared usage by multiple chat members – to create live whiteboards, group orders, multiplayer games and similar apps.

By default, the main Mini App opens to full-screen height, and users cannot reduce them to half-height. However, you can change this behavior via @BotFather or by including the parameter mode=compact in the link to the Mini App, in which case it will open to half-screen height by default.

Good for:

Fully-fledged web services and integrations that any user can open in one tap.
Cooperative, multiplayer or teamwork-oriented services within a chat context.
The use cases are effectively unlimited.
Successful bots which enable a main Mini App and accept payments in Telegram Stars may be featured in the Telegram Mini App Store. To increase the chances of being featured, we recommend uploading high-quality media showcasing your app on your bot's profile and following our design guidelines.

Inline Mode Mini Apps
TL;DR: Mini Apps launched via web_app type InlineQueryResultsButton can be used anywhere in inline mode. Users can create content in a web interface and then seamlessly send it to the current chat via inline mode.

You can use the button parameter in the answerInlineQuery method to display a special 'Switch to Mini App' button either above or in place of the inline results. This button will open a Mini App from the specified URL. Once done, you can call the Telegram.WebApp.switchInlineQuery method to send the user back to inline mode.

Inline Mini Apps have no access to the chat – they can't read messages or send new ones on behalf of the user. To send messages, the user must be redirected to inline mode and actively pick a result.

Good for:

Fully-fledged web services and integrations in inline mode.
Direct Link Mini Apps
TL;DR: Mini App Bots can be launched from a direct link in any chat. They support a startapp parameter and are aware of the current chat context.

You can use direct links to open a Mini App directly in the current chat. If a non-empty startapp parameter is included in the link, it will be passed to the Mini App in the start_param field and in the GET parameter tgWebAppStartParam.

In this mode, Mini Apps can use the chat_type and chat_instance parameters to keep track of the current chat context. This introduces support for concurrent and shared usage by multiple chat members – to create live whiteboards, group orders, multiplayer games and similar apps.

Mini Apps opened from a direct link have no access to the chat – they can't read messages or send new ones on behalf of the user. To send messages, the user must be redirected to inline mode and actively pick a result.

Starting from Bot API 7.6, by default, Mini Apps of this type open to full-screen height, and users cannot reduce them to half-height. However, you can change this behavior by including the parameter mode=compact in the link to the Mini App, in which case it will open to half-screen height by default.

Examples

https://t.me/botusername/appname
https://t.me/botusername/appname?startapp=command
https://t.me/botusername/appname?startapp=command&mode=compact

Good for:

Fully-fledged web services and integrations that any user can open in one tap.
Cooperative, multiplayer or teamwork-oriented services within a chat context.
The use cases are effectively unlimited.
Launching Mini Apps from the Attachment Menu
TL;DR: Mini App Bots can request to be added directly to a user's attachment menu, allowing them to be quickly launched from any chat. To try this mode, open this attachment menu link for @DurgerKingBot, then use the Attach menu in any type of chat.

Mini App Bots can request to be added directly to a user's attachment menu, allowing them to be quickly launched from any type of chat. You can configure in which types of chats your mini app can be started from the attachment menu (private, groups, supergroups or channels).

Attachment menu integration is currently only available for major advertisers on the Telegram Ad Platform. However, all bots can use it in the test server environment.

To enable this feature for your bot, open @BotFather from an account on the test server and send the /setattach command – or go to Bot Settings > Configure Attachment Menu. Then specify the URL that will be opened to launch the bot's Mini App via its icon in the attachment menu.

You can add a 'Settings' item to the context menu of your Mini App using @BotFather. When users select this option from the menu, your bot will receive a settingsButtonClicked event.

In addition to the user's theme settings, the bot will receive basic user information (ID, name, username, language_code, photo), as well as public info about the chat partner (ID, name, username, photo) or the chat info (ID, type, title, username, photo) and a unique identifier for the web view session query_id, which allows messages of any type to be sent to the chat on behalf of the user that opened the bot.

The bot can call the Bot API method answerWebAppQuery, which sends an inline message from the user via the bot to the chat where it was launched and closes the Mini App.

You can read more about adding bots to the attachment menu here.

Initializing Mini Apps
To connect your Mini App to the Telegram client, place the script telegram-web-app.js in the <head> tag before any other scripts, using this code:

<script src="https://telegram.org/js/telegram-web-app.js?62"></script>
Once the script is connected, a window.Telegram.WebApp object will become available with the following fields:

Field	Type	Description
initData	String	A string with raw data transferred to the Mini App, convenient for validating data.
WARNING: Validate data from this field before using it on the bot's server.
initDataUnsafe	WebAppInitData	An object with input data transferred to the Mini App.
WARNING: Data from this field should not be trusted. You should only use data from initData on the bot's server and only after it has been validated.
version	String	The version of the Bot API available in the user's Telegram app.
platform	String	The name of the platform of the user's Telegram app.
colorScheme	String	The color scheme currently used in the Telegram app. Either “light” or “dark”.
Also available as the CSS variable var(--tg-color-scheme).
themeParams	ThemeParams	An object containing the current theme settings used in the Telegram app.
isActive NEW	Boolean	Bot API 8.0+ True, if the Mini App is currently active. False, if the Mini App is minimized.
isExpanded	Boolean	True, if the Mini App is expanded to the maximum available height. False, if the Mini App occupies part of the screen and can be expanded to the full height using the expand() method.
viewportHeight	Float	The current height of the visible area of the Mini App. Also available in CSS as the variable var(--tg-viewport-height).

The application can display just the top part of the Mini App, with its lower part remaining outside the screen area. From this position, the user can “pull” the Mini App to its maximum height, while the bot can do the same by calling the expand() method. As the position of the Mini App changes, the current height value of the visible area will be updated in real time.

Please note that the refresh rate of this value is not sufficient to smoothly follow the lower border of the window. It should not be used to pin interface elements to the bottom of the visible area. It's more appropriate to use the value of the viewportStableHeight field for this purpose.
viewportStableHeight	Float	The height of the visible area of the Mini App in its last stable state. Also available in CSS as a variable var(--tg-viewport-stable-height).

The application can display just the top part of the Mini App, with its lower part remaining outside the screen area. From this position, the user can “pull” the Mini App to its maximum height, while the bot can do the same by calling the expand() method. Unlike the value of viewportHeight, the value of viewportStableHeight does not change as the position of the Mini App changes with user gestures or during animations. The value of viewportStableHeight will be updated after all gestures and animations are completed and the Mini App reaches its final size.

Note the event viewportChanged with the passed parameter isStateStable=true, which will allow you to track when the stable state of the height of the visible area changes.
headerColor	String	Current header color in the #RRGGBB format.
backgroundColor	String	Current background color in the #RRGGBB format.
bottomBarColor	String	Current bottom bar color in the #RRGGBB format.
isClosingConfirmationEnabled	Boolean	True, if the confirmation dialog is enabled while the user is trying to close the Mini App. False, if the confirmation dialog is disabled.
isVerticalSwipesEnabled	Boolean	True, if vertical swipes to close or minimize the Mini App are enabled. False, if vertical swipes to close or minimize the Mini App are disabled. In any case, the user will still be able to minimize and close the Mini App by swiping the Mini App's header.
isFullscreen NEW	Boolean	True, if the Mini App is currently being displayed in fullscreen mode.
isOrientationLocked NEW	Boolean	True, if the Mini App’s orientation is currently locked. False, if orientation changes freely based on the device’s rotation.
safeAreaInset NEW	SafeAreaInset	An object representing the device's safe area insets, accounting for system UI elements like notches or navigation bars.
contentSafeAreaInset NEW	ContentSafeAreaInset	An object representing the safe area for displaying content within the app, free from overlapping Telegram UI elements.
BackButton	BackButton	An object for controlling the back button which can be displayed in the header of the Mini App in the Telegram interface.
MainButton	BottomButton	An object for controlling the main button, which is displayed at the bottom of the Mini App in the Telegram interface.
SecondaryButton	BottomButton	An object for controlling the secondary button, which is displayed at the bottom of the Mini App in the Telegram interface.
SettingsButton	SettingsButton	An object for controlling the Settings item in the context menu of the Mini App in the Telegram interface.
HapticFeedback	HapticFeedback	An object for controlling haptic feedback.
CloudStorage	CloudStorage	An object for controlling cloud storage.
BiometricManager	BiometricManager	An object for controlling biometrics on the device.
Accelerometer NEW	Accelerometer	An object for accessing accelerometer data on the device.
DeviceOrientation NEW	DeviceOrientation	An object for accessing device orientation data on the device.
Gyroscope NEW	Gyroscope	An object for accessing gyroscope data on the device.
LocationManager NEW	LocationManager	An object for controlling location on the device.
DeviceStorage NEW	DeviceStorage	An object for storing and retrieving data from the device's local storage.
SecureStorage NEW	SecureStorage	An object for storing and retrieving data from the device's secure storage.
isVersionAtLeast(version)	Function	Returns true if the user's app supports a version of the Bot API that is equal to or higher than the version passed as the parameter.
setHeaderColor(color)	Function	Bot API 6.1+ A method that sets the app header color in the #RRGGBB format. You can also use keywords bg_color and secondary_bg_color.

Up to Bot API 6.9 You can only pass Telegram.WebApp.themeParams.bg_color or Telegram.WebApp.themeParams.secondary_bg_color as a color or bg_color, secondary_bg_color keywords.
setBackgroundColor(color)	Function	Bot API 6.1+ A method that sets the app background color in the #RRGGBB format. You can also use keywords bg_color and secondary_bg_color.
setBottomBarColor(color)	Function	Bot API 7.10+ A method that sets the app's bottom bar color in the #RRGGBB format. You can also use the keywords bg_color, secondary_bg_color, and bottom_bar_bg_color. This color is also applied to the navigation bar on Android.
enableClosingConfirmation()	Function	Bot API 6.2+ A method that enables a confirmation dialog while the user is trying to close the Mini App.
disableClosingConfirmation()	Function	Bot API 6.2+ A method that disables the confirmation dialog while the user is trying to close the Mini App.
enableVerticalSwipes()	Function	Bot API 7.7+ A method that enables vertical swipes to close or minimize the Mini App. For user convenience, it is recommended to always enable swipes unless they conflict with the Mini App's own gestures.
disableVerticalSwipes()	Function	Bot API 7.7+ A method that disables vertical swipes to close or minimize the Mini App. This method is useful if your Mini App uses swipe gestures that may conflict with the gestures for minimizing and closing the app.
requestFullscreen() NEW	Function	Bot API 8.0+ A method that requests opening the Mini App in fullscreen mode. Although the header is transparent in fullscreen mode, it is recommended that the Mini App sets the header color using the setHeaderColor method. This color helps determine a contrasting color for the status bar and other UI controls.
exitFullscreen() NEW	Function	Bot API 8.0+ A method that requests exiting fullscreen mode.
lockOrientation() NEW	Function	Bot API 8.0+ A method that locks the Mini App’s orientation to its current mode (either portrait or landscape). Once locked, the orientation remains fixed, regardless of device rotation. This is useful if a stable orientation is needed during specific interactions.
unlockOrientation() NEW	Function	Bot API 8.0+ A method that unlocks the Mini App’s orientation, allowing it to follow the device's rotation freely. Use this to restore automatic orientation adjustments based on the device orientation.
addToHomeScreen() NEW	Function	Bot API 8.0+ A method that prompts the user to add the Mini App to the home screen. After successfully adding the icon, the homeScreenAdded event will be triggered if supported by the device. Note that if the device cannot determine the installation status, the event may not be received even if the icon has been added.
checkHomeScreenStatus([callback]) NEW	Function	Bot API 8.0+ A method that checks if adding to the home screen is supported and if the Mini App has already been added. If an optional callback parameter is provided, the callback function will be called with a single argument status, which is a string indicating the home screen status. Possible values for status are:
- unsupported – the feature is not supported, and it is not possible to add the icon to the home screen,
- unknown – the feature is supported, and the icon can be added, but it is not possible to determine if the icon has already been added,
- added – the icon has already been added to the home screen,
- missed – the icon has not been added to the home screen.
onEvent(eventType, eventHandler)	Function	A method that sets the app event handler. Check the list of available events.
offEvent(eventType, eventHandler)	Function	A method that deletes a previously set event handler.
sendData(data)	Function	A method used to send data to the bot. When this method is called, a service message is sent to the bot containing the data data of the length up to 4096 bytes, and the Mini App is closed. See the field web_app_data in the class Message.

This method is only available for Mini Apps launched via a Keyboard button.
switchInlineQuery(query[, choose_chat_types])	Function	Bot API 6.7+ A method that inserts the bot's username and the specified inline query in the current chat's input field. Query may be empty, in which case only the bot's username will be inserted. If an optional choose_chat_types parameter was passed, the client prompts the user to choose a specific chat, then opens that chat and inserts the bot's username and the specified inline query in the input field. You can specify which types of chats the user will be able to choose from. It can be one or more of the following types: users, bots, groups, channels.
openLink(url[, options])	Function	A method that opens a link in an external browser. The Mini App will not be closed.
Bot API 6.4+ If the optional options parameter is passed with the field try_instant_view=true, the link will be opened in Instant View mode if possible.

Note that this method can be called only in response to user interaction with the Mini App interface (e.g. a click inside the Mini App or on the main button)
openTelegramLink(url)	Function	A method that opens a telegram link inside the Telegram app. The Mini App will not be closed after this method is called.

Up to Bot API 7.0 The Mini App will be closed after this method is called.
openInvoice(url[, callback])	Function	Bot API 6.1+ A method that opens an invoice using the link url. The Mini App will receive the event invoiceClosed when the invoice is closed. If an optional callback parameter was passed, the callback function will be called and the invoice status will be passed as the first argument.
shareToStory(media_url[, params])	Function	Bot API 7.8+ A method that opens the native story editor with the media specified in the media_url parameter as an HTTPS URL. An optional params argument of the type StoryShareParams describes additional sharing settings.
shareMessage(msg_id[, callback]) NEW	Function	Bot API 8.0+ A method that opens a dialog allowing the user to share a message provided by the bot. If an optional callback parameter is provided, the callback function will be called with a boolean as the first argument, indicating whether the message was successfully sent. The message id passed to this method must belong to a PreparedInlineMessage previously obtained via the Bot API method savePreparedInlineMessage.
setEmojiStatus(custom_emoji_id[, params, callback])	Function	Bot API 8.0+ A method that opens a dialog allowing the user to set the specified custom emoji as their status. An optional params argument of type EmojiStatusParams specifies additional settings, such as duration. If an optional callback parameter is provided, the callback function will be called with a boolean as the first argument, indicating whether the status was set.

Note: this method opens a native dialog and cannot be used to set the emoji status without manual user interaction. For fully programmatic changes, you should instead use the Bot API method setUserEmojiStatus after obtaining authorization to do so via the Mini App method requestEmojiStatusAccess.
requestEmojiStatusAccess([callback]) NEW	Function	Bot API 8.0+ A method that shows a native popup requesting permission for the bot to manage user's emoji status. If an optional callback parameter was passed, the callback function will be called when the popup is closed and the first argument will be a boolean indicating whether the user granted this access.
downloadFile(params[, callback]) NEW	Function	Bot API 8.0+ A method that displays a native popup prompting the user to download a file specified by the params argument of type DownloadFileParams. If an optional callback parameter is provided, the callback function will be called when the popup is closed, with the first argument as a boolean indicating whether the user accepted the download request.
hideKeyboard() NEW	Function	Bot API 9.1+ A method that hides the on-screen keyboard, if it is currently visible. Does nothing if the keyboard is not active.
showPopup(params[, callback])	Function	Bot API 6.2+ A method that shows a native popup described by the params argument of the type PopupParams. The Mini App will receive the event popupClosed when the popup is closed. If an optional callback parameter was passed, the callback function will be called and the field id of the pressed button will be passed as the first argument.
showAlert(message[, callback])	Function	Bot API 6.2+ A method that shows message in a simple alert with a 'Close' button. If an optional callback parameter was passed, the callback function will be called when the popup is closed.
showConfirm(message[, callback])	Function	Bot API 6.2+ A method that shows message in a simple confirmation window with 'OK' and 'Cancel' buttons. If an optional callback parameter was passed, the callback function will be called when the popup is closed and the first argument will be a boolean indicating whether the user pressed the 'OK' button.
showScanQrPopup(params[, callback])	Function	Bot API 6.4+ A method that shows a native popup for scanning a QR code described by the params argument of the type ScanQrPopupParams. The Mini App will receive the event qrTextReceived every time the scanner catches a code with text data. If an optional callback parameter was passed, the callback function will be called and the text from the QR code will be passed as the first argument. Returning true inside this callback function causes the popup to be closed. Starting from Bot API 7.7, the Mini App will receive the scanQrPopupClosed event if the user closes the native popup for scanning a QR code.
closeScanQrPopup()	Function	Bot API 6.4+ A method that closes the native popup for scanning a QR code opened with the showScanQrPopup method. Run it if you received valid data in the event qrTextReceived.
readTextFromClipboard([callback])	Function	Bot API 6.4+ A method that requests text from the clipboard. The Mini App will receive the event clipboardTextReceived. If an optional callback parameter was passed, the callback function will be called and the text from the clipboard will be passed as the first argument.

Note: this method can be called only for Mini Apps launched from the attachment menu and only in response to a user interaction with the Mini App interface (e.g. a click inside the Mini App or on the main button).
requestWriteAccess([callback])	Function	Bot API 6.9+ A method that shows a native popup requesting permission for the bot to send messages to the user. If an optional callback parameter was passed, the callback function will be called when the popup is closed and the first argument will be a boolean indicating whether the user granted this access.
requestContact([callback])	Function	Bot API 6.9+ A method that shows a native popup prompting the user for their phone number. If an optional callback parameter was passed, the callback function will be called when the popup is closed and the first argument will be a boolean indicating whether the user shared its phone number.
requestChat(req_id[, callback]) NEW	Function	Bot API 9.6+ A method that opens a dialog allowing the user to select an existing chat or create a new one. If an optional callback parameter is provided, the callback function will be called with a boolean as the first argument, indicating whether the message was successfully sent. The request id passed to this method must belong to a PreparedKeyboardButton previously obtained via the Bot API method savePreparedKeyboardButton.
ready()	Function	A method that informs the Telegram app that the Mini App is ready to be displayed.
It is recommended to call this method as early as possible, as soon as all essential interface elements are loaded. Once this method is called, the loading placeholder is hidden and the Mini App is shown.
If the method is not called, the placeholder will be hidden only when the page is fully loaded.
expand()	Function	A method that expands the Mini App to the maximum available height. To find out if the Mini App is expanded to the maximum height, refer to the value of the Telegram.WebApp.isExpanded parameter
close()	Function	A method that closes the Mini App.
ThemeParams
Mini Apps can adjust the appearance of the interface to match the Telegram user's app in real time. This object contains the user's current theme settings:

Field	Type	Description
bg_color	String	Optional. Background color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-bg-color).
text_color	String	Optional. Main text color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-text-color).
hint_color	String	Optional. Hint text color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-hint-color).
link_color	String	Optional. Link color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-link-color).
button_color	String	Optional. Button color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-button-color).
button_text_color	String	Optional. Button text color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-button-text-color).
secondary_bg_color	String	Optional. Bot API 6.1+ Secondary background color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-secondary-bg-color).
header_bg_color	String	Optional. Bot API 7.0+ Header background color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-header-bg-color).
bottom_bar_bg_color	String	Optional. Bot API 7.10+ Bottom background color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-bottom-bar-bg-color).
accent_text_color	String	Optional. Bot API 7.0+ Accent text color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-accent-text-color).
section_bg_color	String	Optional. Bot API 7.0+ Background color for the section in the #RRGGBB format. It is recommended to use this in conjunction with secondary_bg_color.
Also available as the CSS variable var(--tg-theme-section-bg-color).
section_header_text_color	String	Optional. Bot API 7.0+ Header text color for the section in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-section-header-text-color).
section_separator_color	String	Optional. Bot API 7.6+ Section separator color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-section-separator-color).
subtitle_text_color	String	Optional. Bot API 7.0+ Subtitle text color in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-subtitle-text-color).
destructive_text_color	String	Optional. Bot API 7.0+ Text color for destructive actions in the #RRGGBB format.
Also available as the CSS variable var(--tg-theme-destructive-text-color).
WebViewColors explained
StoryShareParams
This object describes additional sharing settings for the native story editor.

Field	Type	Description
text	String	Optional. The caption to be added to the media, 0-200 characters for regular users and 0-2048 characters for premium subscribers.
widget_link	StoryWidgetLink	Optional. An object that describes a widget link to be included in the story. Note that only premium subscribers can post stories with links.
StoryWidgetLink
This object describes a widget link to be included in the story.

Field	Type	Description
url	String	The URL to be included in the story.
name	String	Optional. The name to be displayed for the widget link, 0-48 characters.
ScanQrPopupParams
This object describes the native popup for scanning QR codes.

Field	Type	Description
text	String	Optional. The text to be displayed under the 'Scan QR' heading, 0-64 characters.
PopupParams
This object describes the native popup.

Field	Type	Description
title	String	Optional. The text to be displayed in the popup title, 0-64 characters.
message	String	The message to be displayed in the body of the popup, 1-256 characters.
buttons	Array of PopupButton	Optional. List of buttons to be displayed in the popup, 1-3 buttons. Set to [{“type”:“close”}] by default.
PopupButton
This object describes the native popup button.

Field	Type	Description
id	String	Optional. Identifier of the button, 0-64 characters. Set to empty string by default.
If the button is pressed, its id is returned in the callback and the popupClosed event.
type	String	Optional. Type of the button. Set to default by default.
Can be one of these values:
- default, a button with the default style,
- ok, a button with the localized text “OK”,
- close, a button with the localized text “Close”,
- cancel, a button with the localized text “Cancel”,
- destructive, a button with a style that indicates a destructive action (e.g. “Remove”, “Delete”, etc.).
text	String	Optional. The text to be displayed on the button, 0-64 characters. Required if type is default or destructive. Irrelevant for other types.
EmojiStatusParams
This object describes additional settings for setting an emoji status.

Field	Type	Description
duration	Integer	Optional. The duration for which the status will remain set, in seconds.
DownloadFileParams
This object describes the parameters for the file download request.

Note: To ensure consistent file download behavior across platforms, include the HTTP headers Content-Disposition: attachment; filename="<file_name>" and Access-Control-Allow-Origin: https://web.telegram.org in the server response. Without these headers, the download may not work as expected, especially on web platforms.

Field	Type	Description
url	String	The HTTPS URL of the file to be downloaded.
file_name	String	The suggested name for the downloaded file.
SafeAreaInset
This object represents the system-defined safe area insets, providing padding values to ensure content remains within visible boundaries, avoiding overlap with system UI elements like notches or navigation bars.

Field	Type	Description
top	Integer	The top inset in pixels, representing the space to avoid at the top of the screen. Also available as the CSS variable var(--tg-safe-area-inset-top).
bottom	Integer	The bottom inset in pixels, representing the space to avoid at the bottom of the screen. Also available as the CSS variable var(--tg-safe-area-inset-bottom).
left	Integer	The left inset in pixels, representing the space to avoid on the left side of the screen. Also available as the CSS variable var(--tg-safe-area-inset-left).
right	Integer	The right inset in pixels, representing the space to avoid on the right side of the screen. Also available as the CSS variable var(--tg-safe-area-inset-right).
SafeAreaInset explained
ContentSafeAreaInset
This object represents the content-defined safe area insets, providing padding values to ensure content remains within visible boundaries, avoiding overlap with Telegram UI elements.

Field	Type	Description
top	Integer	The top inset in pixels, representing the space to avoid at the top of the content area. Also available as the CSS variable var(--tg-content-safe-area-inset-top).
bottom	Integer	The bottom inset in pixels, representing the space to avoid at the bottom of the content area. Also available as the CSS variable var(--tg-content-safe-area-inset-bottom).
left	Integer	The left inset in pixels, representing the space to avoid on the left side of the content area. Also available as the CSS variable var(--tg-content-safe-area-inset-left).
right	Integer	The right inset in pixels, representing the space to avoid on the right side of the content area. Also available as the CSS variable var(--tg-content-safe-area-inset-right).
ContentSafeAreaInset explained
BackButton
This object controls the back button, which can be displayed in the header of the Mini App in the Telegram interface.

Field	Type	Description
isVisible	Boolean	Shows whether the button is visible. Set to false by default.
onClick(callback)	Function	Bot API 6.1+ A method that sets the button press event handler. An alias for Telegram.WebApp.onEvent('backButtonClicked', callback)
offClick(callback)	Function	Bot API 6.1+ A method that removes the button press event handler. An alias for Telegram.WebApp.offEvent('backButtonClicked', callback)
show()	Function	Bot API 6.1+ A method to make the button active and visible.
hide()	Function	Bot API 6.1+ A method to hide the button.
All these methods return the BackButton object so they can be chained.

BottomButton
This object controls the button that is displayed at the bottom of the Mini App in the Telegram interface.

Field	Type	Description
type	String	Readonly. Type of the button. It can be either main for the main button or secondary for the secondary button.
iconCustomEmojiId	String	Bot API 9.5+ Unique identifier of the custom emoji shown before the text of the button.
text	String	Current button text. Set to Continue for the main button and Cancel for the secondary button by default.
color	String	Current button color. Set to themeParams.button_color for the main button and themeParams.bottom_bar_bg_color for the secondary button by default.
textColor	String	Current button text color. Set to themeParams.button_text_color for the main button and themeParams.button_color for the secondary button by default.
isVisible	Boolean	Shows whether the button is visible. Set to false by default.
isActive	Boolean	Shows whether the button is active. Set to true by default.
hasShineEffect	Boolean	Bot API 7.10+ Shows whether the button has a shine effect. Set to false by default.
position	String	Bot API 7.10+ Position of the secondary button. Not defined for the main button. It applies only if both the main and secondary buttons are visible. Set to left by default.
Supported values:
- left, displayed to the left of the main button,
- right, displayed to the right of the main button,
- top, displayed above the main button,
- bottom, displayed below the main button.
isProgressVisible	Boolean	Readonly. Shows whether the button is displaying a loading indicator.
setText(text)	Function	A method to set the button text.
onClick(callback)	Function	A method that sets the button's press event handler. An alias for Telegram.WebApp.onEvent('mainButtonClicked', callback)
offClick(callback)	Function	A method that removes the button's press event handler. An alias for Telegram.WebApp.offEvent('mainButtonClicked', callback)
show()	Function	A method to make the button visible.
Note that opening the Mini App from the attachment menu hides the main button until the user interacts with the Mini App interface.
hide()	Function	A method to hide the button.
enable()	Function	A method to enable the button.
disable()	Function	A method to disable the button.
showProgress(leaveActive)	Function	A method to show a loading indicator on the button.
It is recommended to display loading progress if the action tied to the button may take a long time. By default, the button is disabled while the action is in progress. If the parameter leaveActive=true is passed, the button remains enabled.
hideProgress()	Function	A method to hide the loading indicator.
setParams(params)	Function	A method to set the button parameters. The params parameter is an object containing one or several fields that need to be changed:
icon_custom_emoji_id - Bot API 9.5+ button icon emoji id;
text - button text;
color - button color;
text_color - button text color;
has_shine_effect - Bot API 7.10+ enable shine effect;
position - position of the secondary button;
is_active - enable the button;
is_visible - show the button.
All these methods return the BottomButton object so they can be chained.

SettingsButton
This object controls the Settings item in the context menu of the Mini App in the Telegram interface.

Field	Type	Description
isVisible	Boolean	Shows whether the context menu item is visible. Set to false by default.
onClick(callback)	Function	Bot API 7.0+ A method that sets the press event handler for the Settings item in the context menu. An alias for Telegram.WebApp.onEvent('settingsButtonClicked', callback)
offClick(callback)	Function	Bot API 7.0+ A method that removes the press event handler from the Settings item in the context menu. An alias for Telegram.WebApp.offEvent('settingsButtonClicked', callback)
show()	Function	Bot API 7.0+ A method to make the Settings item in the context menu visible.
hide()	Function	Bot API 7.0+ A method to hide the Settings item in the context menu.
All these methods return the SettingsButton object so they can be chained.

HapticFeedback
This object controls haptic feedback.

Field	Type	Description
impactOccurred(style)	Function	Bot API 6.1+ A method tells that an impact occurred. The Telegram app may play the appropriate haptics based on style value passed. Style can be one of these values:
- light, indicates a collision between small or lightweight UI objects,
- medium, indicates a collision between medium-sized or medium-weight UI objects,
- heavy, indicates a collision between large or heavyweight UI objects,
- rigid, indicates a collision between hard or inflexible UI objects,
- soft, indicates a collision between soft or flexible UI objects.
notificationOccurred(type)	Function	Bot API 6.1+ A method tells that a task or action has succeeded, failed, or produced a warning. The Telegram app may play the appropriate haptics based on type value passed. Type can be one of these values:
- error, indicates that a task or action has failed,
- success, indicates that a task or action has completed successfully,
- warning, indicates that a task or action produced a warning.
selectionChanged()	Function	Bot API 6.1+ A method tells that the user has changed a selection. The Telegram app may play the appropriate haptics.

Do not use this feedback when the user makes or confirms a selection; use it only when the selection changes.
All these methods return the HapticFeedback object so they can be chained.

CloudStorage
This object controls the cloud storage. Each bot can store up to 1024 items per user in the cloud storage.

Field	Type	Description
setItem(key, value[, callback])	Function	Bot API 6.9+ A method that stores a value in the cloud storage using the specified key. The key should contain 1-128 characters, only A-Z, a-z, 0-9, _ and - are allowed. The value should contain 0-4096 characters. You can store up to 1024 keys in the cloud storage. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether the value was stored.
getItem(key, callback)	Function	Bot API 6.9+ A method that receives a value from the cloud storage using the specified key. The key should contain 1-128 characters, only A-Z, a-z, 0-9, _ and - are allowed. In case of an error, the callback function will be called and the first argument will contain the error. In case of success, the first argument will be null and the value will be passed as the second argument.
getItems(keys, callback)	Function	Bot API 6.9+ A method that receives values from the cloud storage using the specified keys. The keys should contain 1-128 characters, only A-Z, a-z, 0-9, _ and - are allowed. In case of an error, the callback function will be called and the first argument will contain the error. In case of success, the first argument will be null and the values will be passed as the second argument.
removeItem(key[, callback])	Function	Bot API 6.9+ A method that removes a value from the cloud storage using the specified key. The key should contain 1-128 characters, only A-Z, a-z, 0-9, _ and - are allowed. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether the value was removed.
removeItems(keys[, callback])	Function	Bot API 6.9+ A method that removes values from the cloud storage using the specified keys. The keys should contain 1-128 characters, only A-Z, a-z, 0-9, _ and - are allowed. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether the values were removed.
getKeys(callback)	Function	Bot API 6.9+ A method that receives the list of all keys stored in the cloud storage. In case of an error, the callback function will be called and the first argument will contain the error. In case of success, the first argument will be null and the list of keys will be passed as the second argument.
All these methods return the CloudStorage object, so they can be chained.

BiometricManager
This object controls biometrics on the device. Before the first use of this object, it needs to be initialized using the init method.

Field	Type	Description
isInited	Boolean	Shows whether biometrics object is initialized.
isBiometricAvailable	Boolean	Shows whether biometrics is available on the current device.
biometricType	String	The type of biometrics currently available on the device. Can be one of these values:
- finger, fingerprint-based biometrics,
- face, face-based biometrics,
- unknown, biometrics of an unknown type.
isAccessRequested	Boolean	Shows whether permission to use biometrics has been requested.
isAccessGranted	Boolean	Shows whether permission to use biometrics has been granted.
isBiometricTokenSaved	Boolean	Shows whether the token is saved in secure storage on the device.
deviceId	String	A unique device identifier that can be used to match the token to the device.
init([callback])	Function	Bot API 7.2+ A method that initializes the BiometricManager object. It should be called before the object's first use. If an optional callback parameter was passed, the callback function will be called when the object is initialized.
requestAccess(params[, callback])	Function	Bot API 7.2+ A method that requests permission to use biometrics according to the params argument of type BiometricRequestAccessParams. If an optional callback parameter was passed, the callback function will be called and the first argument will be a boolean indicating whether the user granted access.
authenticate(params[, callback])	Function	Bot API 7.2+ A method that authenticates the user using biometrics according to the params argument of type BiometricAuthenticateParams. If an optional callback parameter was passed, the callback function will be called and the first argument will be a boolean indicating whether the user authenticated successfully. If so, the second argument will be a biometric token.
updateBiometricToken(token, [callback])	Function	Bot API 7.2+ A method that updates the biometric token in secure storage on the device. To remove the token, pass an empty string. If an optional callback parameter was passed, the callback function will be called and the first argument will be a boolean indicating whether the token was updated.
openSettings()	Function	Bot API 7.2+ A method that opens the biometric access settings for bots. Useful when you need to request biometrics access to users who haven't granted it yet.

Note that this method can be called only in response to user interaction with the Mini App interface (e.g. a click inside the Mini App or on the main button)
All these methods return the BiometricManager object so they can be chained.

BiometricRequestAccessParams
This object describes the native popup for requesting permission to use biometrics.

Field	Type	Description
reason	String	Optional. The text to be displayed to a user in the popup describing why the bot needs access to biometrics, 0-128 characters.
BiometricAuthenticateParams
This object describes the native popup for authenticating the user using biometrics.

Field	Type	Description
reason	String	Optional. The text to be displayed to a user in the popup describing why you are asking them to authenticate and what action you will be taking based on that authentication, 0-128 characters.
Accelerometer
This object provides access to accelerometer data on the device.

Field	Type	Description
isStarted	Boolean	Indicates whether accelerometer tracking is currently active.
x	Float	The current acceleration in the X-axis, measured in m/s².
y	Float	The current acceleration in the Y-axis, measured in m/s².
z	Float	The current acceleration in the Z-axis, measured in m/s².
start(params[, callback])	Function	Bot API 8.0+ Starts tracking accelerometer data using params of type AccelerometerStartParams. If an optional callback parameter is provided, the callback function will be called with a boolean indicating whether tracking was successfully started.
stop([callback])	Function	Bot API 8.0+ Stops tracking accelerometer data. If an optional callback parameter is provided, the callback function will be called with a boolean indicating whether tracking was successfully stopped.
All these methods return the Accelerometer object so they can be chained.

Accelerometer
AccelerometerStartParams
This object defines the parameters for starting accelerometer tracking.

Field	Type	Description
refresh_rate	Integer	Optional. The refresh rate in milliseconds, with acceptable values ranging from 20 to 1000. Set to 1000 by default. Note that refresh_rate may not be supported on all platforms, so the actual tracking frequency may differ from the specified value.
DeviceOrientation
This object provides access to orientation data on the device.

Field	Type	Description
isStarted	Boolean	Indicates whether device orientation tracking is currently active.
absolute	Boolean	A boolean that indicates whether or not the device is providing orientation data in absolute values.
alpha	Float	The rotation around the Z-axis, measured in radians.
beta	Float	The rotation around the X-axis, measured in radians.
gamma	Float	The rotation around the Y-axis, measured in radians.
start(params[, callback])	Function	Bot API 8.0+ Starts tracking device orientation data using params of type DeviceOrientationStartParams. If an optional callback parameter is provided, the callback function will be called with a boolean indicating whether tracking was successfully started.
stop([callback])	Function	Bot API 8.0+ Stops tracking device orientation data. If an optional callback parameter is provided, the callback function will be called with a boolean indicating whether tracking was successfully stopped.
All these methods return the DeviceOrientation object so they can be chained.

DeviceOrientation
DeviceOrientationStartParams
This object defines the parameters for starting device orientation tracking.

Field	Type	Description
refresh_rate	Integer	Optional. The refresh rate in milliseconds, with acceptable values ranging from 20 to 1000. Set to 1000 by default. Note that refresh_rate may not be supported on all platforms, so the actual tracking frequency may differ from the specified value.
need_absolute	Boolean	Optional. Pass true to receive absolute orientation data, allowing you to determine the device's attitude relative to magnetic north. Use this option if implementing features like a compass in your app. If relative data is sufficient, pass false. Set to false by default.

Note: Keep in mind that some devices may not support absolute orientation data. In such cases, you will receive relative data even if need_absolute=true is passed. Check the DeviceOrientation.absolute parameter to determine whether the data provided is absolute or relative.
Gyroscope
This object provides access to gyroscope data on the device.

Field	Type	Description
isStarted	Boolean	Indicates whether gyroscope tracking is currently active.
x	Float	The current rotation rate around the X-axis, measured in rad/s.
y	Float	The current rotation rate around the Y-axis, measured in rad/s.
z	Float	The current rotation rate around the Z-axis, measured in rad/s.
start(params[, callback])	Function	Bot API 8.0+ Starts tracking gyroscope data using params of type GyroscopeStartParams. If an optional callback parameter is provided, the callback function will be called with a boolean indicating whether tracking was successfully started.
stop([callback])	Function	Bot API 8.0+ Stops tracking gyroscope data. If an optional callback parameter is provided, the callback function will be called with a boolean indicating whether tracking was successfully stopped.
All these methods return the Gyroscope object so they can be chained.

Gyroscope
GyroscopeStartParams
This object defines the parameters for starting gyroscope tracking.

Field	Type	Description
refresh_rate	Integer	Optional. The refresh rate in milliseconds, with acceptable values ranging from 20 to 1000. Set to 1000 by default. Note that refresh_rate may not be supported on all platforms, so the actual tracking frequency may differ from the specified value.
LocationManager
This object controls location access on the device. Before the first use of this object, it needs to be initialized using the init method.

Field	Type	Description
isInited	Boolean	Shows whether the LocationManager object has been initialized.
isLocationAvailable	Boolean	Shows whether location services are available on the current device.
isAccessRequested	Boolean	Shows whether permission to use location has been requested.
isAccessGranted	Boolean	Shows whether permission to use location has been granted.
init([callback])	Function	Bot API 8.0+ A method that initializes the LocationManager object. It should be called before the object's first use. If an optional callback parameter is provided, the callback function will be called when the object is initialized.
getLocation(callback)	Function	Bot API 8.0+ A method that requests location data. The callback function will be called with null as the first argument if access to location was not granted, or an object of type LocationData as the first argument if access was successful.
openSettings()	Function	Bot API 8.0+ A method that opens the location access settings for bots. Useful when you need to request location access from users who haven't granted it yet.

Note that this method can be called only in response to user interaction with the Mini App interface (e.g., a click inside the Mini App or on the main button).
All these methods return the LocationManager object so they can be chained.

LocationData
This object contains data about the current location.

Field	Type	Description
latitude	Float	Latitude in degrees.
longitude	Float	Longitude in degrees.
altitude	Float	Altitude above sea level in meters. null if altitude data is not available on the device.
course	Float	The direction the device is moving in degrees (0 = North, 90 = East, 180 = South, 270 = West). null if course data is not available on the device.
speed	Float	The speed of the device in m/s. null if speed data is not available on the device.
horizontal_accuracy	Float	Accuracy of the latitude and longitude values in meters. null if horizontal accuracy data is not available on the device.
vertical_accuracy	Float	Accuracy of the altitude value in meters. null if vertical accuracy data is not available on the device.
course_accuracy	Float	Accuracy of the course value in degrees. null if course accuracy data is not available on the device.
speed_accuracy	Float	Accuracy of the speed value in m/s. null if speed accuracy data is not available on the device.
DeviceStorage
This object provides access to persistent local storage on the user’s device. It is conceptually similar to the browser's localStorage API, but integrated within the Telegram client. All data is stored locally and is available only to the bot that created it. Each bot can store up to 5 MB per user using this storage.

Field	Type	Description
setItem(key, value[, callback])	Function	Bot API 9.0+ A method that stores a value in the device's local storage using the specified key. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether the value was stored.
getItem(key, callback)	Function	Bot API 9.0+ A method that receives a value from the device's local storage using the specified key. In case of an error, the callback function will be called and the first argument will contain the error. In case of success, the first argument will be null and the value will be passed as the second argument.
removeItem(key[, callback])	Function	Bot API 9.0+ A method that removes a value from the device's local storage using the specified key. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether the value was removed.
clear([callback])	Function	Bot API 9.0+ A method that clears all keys previously stored by the bot in the device's local storage. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether all values were removed.
All these methods return the DeviceStorage object, so they can be chained.

SecureStorage
This object provides access to a secure storage on the user’s device for sensitive data. On iOS, it uses the system Keychain; on Android, it uses the Keystore. This ensures that all stored values are encrypted at rest and inaccessible to unauthorized applications.

Secure storage is suitable for storing tokens, secrets, authentication state, and other sensitive user-specific information. Each bot can store up to 10 items per user.

Field	Type	Description
setItem(key, value[, callback])	Function	Bot API 9.0+ A method that stores a value in the device's secure storage using the specified key. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether the value was stored.
getItem(key, callback)	Function	Bot API 9.0+ A method that receives a value from the device's secure storage using the specified key. In case of an error, the callback function will be called and the first argument will contain the error. In case of success, the first argument will be null and the value will be passed as the second argument. If the key was not found, the second argument will be null, and the third argument will be a boolean indicating whether the key can be restored from the current device.
restoreItem(key[, callback])	Function	Bot API 9.0+ Attempts to restore a key that previously existed on the current device. When called, the user will be asked for permission to restore the value. If the user declines or an error occurs, the first argument in the callback will contain the error. If restored successfully, the first argument will be null and the second argument will contain the restored value.
removeItem(key[, callback])	Function	Bot API 9.0+ A method that removes a value from the device's secure storage using the specified key. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether the value was removed.
clear([callback])	Function	Bot API 9.0+ A method that clears all keys previously stored by the bot in the device's secure storage. If an optional callback parameter was passed, the callback function will be called. In case of an error, the first argument will contain the error. In case of success, the first argument will be null and the second argument will be a boolean indicating whether all values were removed.
All these methods return the SecureStorage object, so they can be chained.

WebAppInitData
This object contains data that is transferred to the Mini App when it is opened. It is empty if the Mini App was launched from a keyboard button or from inline mode.

Field	Type	Description
query_id	String	Optional. A unique identifier for the Mini App session, required for sending messages via the answerWebAppQuery method.
user	WebAppUser	Optional. An object containing data about the current user.
receiver	WebAppUser	Optional. An object containing data about the chat partner of the current user in the chat where the bot was launched via the attachment menu. Returned only for private chats and only for Mini Apps launched via the attachment menu.
chat	WebAppChat	Optional. An object containing data about the chat where the bot was launched via the attachment menu. Returned for supergroups, channels and group chats – only for Mini Apps launched via the attachment menu.
chat_type	String	Optional. Type of the chat from which the Mini App was opened. Can be either “sender” for a private chat with the user opening the link, “private”, “group”, “supergroup”, or “channel”. Returned only for Mini Apps launched from direct links.
chat_instance	String	Optional. Global identifier, uniquely corresponding to the chat from which the Mini App was opened. Returned only for Mini Apps launched from a direct link.
start_param	String	Optional. The value of the startattach parameter, passed via link. Only returned for Mini Apps when launched from the attachment menu via link.

The value of the start_param parameter will also be passed in the GET-parameter tgWebAppStartParam, so the Mini App can load the correct interface right away.
can_send_after	Integer	Optional. Time in seconds, after which a message can be sent via the answerWebAppQuery method.
auth_date	Integer	Unix time when the form was opened.
hash	String	A hash of all passed parameters, which the bot server can use to check their validity.
signature NEW	String	A signature of all passed parameters (except hash), which the third party can use to check their validity.
WebAppUser
This object contains the data of the Mini App user.

Field	Type	Description
id	Integer	A unique identifier for the user or bot. This number may have more than 32 significant bits and some programming languages may have difficulty/silent defects in interpreting it. It has at most 52 significant bits, so a 64-bit integer or a double-precision float type is safe for storing this identifier.
is_bot	Boolean	Optional. True, if this user is a bot. Returns in the receiver field only.
first_name	String	First name of the user or bot.
last_name	String	Optional. Last name of the user or bot.
username	String	Optional. Username of the user or bot.
language_code	String	Optional. IETF language tag of the user's language. Returns in user field only.
is_premium	True	Optional. True, if this user is a Telegram Premium user.
added_to_attachment_menu	True	Optional. True, if this user added the bot to the attachment menu.
allows_write_to_pm	True	Optional. True, if this user allowed the bot to message them.
photo_url	String	Optional. URL of the user’s profile photo. The photo can be in .jpeg or .svg formats.
WebAppChat
This object represents a chat.

Field	Type	Description
id	Integer	Unique identifier for this chat. This number may have more than 32 significant bits and some programming languages may have difficulty/silent defects in interpreting it. But it has at most 52 significant bits, so a signed 64-bit integer or double-precision float type are safe for storing this identifier.
type	String	Type of chat, can be either “group”, “supergroup” or “channel”
title	String	Title of the chat
username	String	Optional. Username of the chat
photo_url	String	Optional. URL of the chat’s photo. The photo can be in .jpeg or .svg formats. Only returned for Mini Apps launched from the attachment menu.
Validating data received via the Mini App
To validate data received via the Mini App, one should send the data from the Telegram.WebApp.initData field to the bot's backend. The data is a query string, which is composed of a series of field-value pairs.

You can verify the integrity of the data received by comparing the received hash parameter with the hexadecimal representation of the HMAC-SHA-256 signature of the data-check-string with the secret key, which is the HMAC-SHA-256 signature of the bot's token with the constant string WebAppData used as a key.

Data-check-string is a chain of all received fields, sorted alphabetically, in the format key=<value> with a line feed character ('\n', 0x0A) used as separator – e.g., 'auth_date=<auth_date>\nquery_id=<query_id>\nuser=<user>'.

The full check might look like:

data_check_string = ...
secret_key = HMAC_SHA256(<bot_token>, "WebAppData")
if (hex(HMAC_SHA256(data_check_string, secret_key)) == hash) {
  // data is from Telegram
}
To prevent the use of outdated data, you can additionally check the auth_date field, which contains a Unix timestamp of when it was received by the Mini App.

Once validated, the data may be used on your server. Complex data types are represented as JSON-serialized objects.

Validating data for Third-Party Use
NEW If you need to share the data with a third party, they can validate the data without requiring access to your bot's token. Simply provide them with the data from the Telegram.WebApp.initData field and your bot_id.

The integrity of the data can be verified by validating the received signature parameter, which is the base64url-encoded representation of the Ed25519 signature of the data-check-string. The verification is performed using the public key provided by Telegram.

Data-check-string is constructed as follows:
1. Prepend the bot_id, followed by : and the constant string WebAppData.
2. Add a line feed character ('\n', 0x0A).
3. Append all received fields (except hash and signature), sorted alphabetically, in the format key=<value>.
4. Separate each key-value pair with a line feed character ('\n', 0x0A).

Example:
'12345678:WebAppData\nauth_date=<auth_date>\nquery_id=<query_id>\nuser=<user>'

The verification process might look like this:

data_check_string = ...
public_key = "<Telegram_public_key>"
if (Ed25519_verify(public_key, data_check_string, signature)) {
  // data is valid and originated from Telegram
}
Telegram provides the following Ed25519 public keys for signature verification:

Test environment: 40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec (hex)
Production: e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d (hex)

To prevent the use of outdated data, the third party should additionally validate the auth_date field. This field contains a Unix timestamp indicating when the data was received by the Mini App.

Once validated, the data may be used. Complex data types are represented as JSON-serialized objects.

Events Available for Mini Apps
The Mini App can receive events from the Telegram app, onto which a handler can be attached using the Telegram.WebApp.onEvent(eventType, eventHandler) method. Inside eventHandler the this object refers to Telegram.WebApp, the set of parameters sent to the handler depends on the event type. Below is a list of possible events:

eventType	Description
activated NEW	Bot API 8.0+ Occurs when the Mini App becomes active (e.g., opened from minimized state or selected among tabs).
eventHandler receives no parameters.
deactivated NEW	Bot API 8.0+ Occurs when the Mini App becomes inactive (e.g., minimized or moved to an inactive tab).
eventHandler receives no parameters.
themeChanged	Occurs whenever theme settings are changed in the user's Telegram app (including switching to night mode).
eventHandler receives no parameters, new theme settings and color scheme can be received via this.themeParams and this.colorScheme respectively.
viewportChanged	Occurs when the visible section of the Mini App is changed.
eventHandler receives an object with the single field isStateStable. If isStateStable is true, the resizing of the Mini App is finished. If it is false, the resizing is ongoing (the user is expanding or collapsing the Mini App or an animated object is playing). The current value of the visible section’s height is available in this.viewportHeight.
safeAreaChanged NEW	Bot API 8.0+ Occurs when the device's safe area insets change (e.g., due to orientation change or screen adjustments).
eventHandler receives no parameters. The current inset values can be accessed via this.safeAreaInset.
contentSafeAreaChanged NEW	Bot API 8.0+ Occurs when the safe area for content changes (e.g., due to orientation change or screen adjustments).
eventHandler receives no parameters. The current inset values can be accessed via this.contentSafeAreaInset.
mainButtonClicked	Occurs when the main button is pressed.
eventHandler receives no parameters.
secondaryButtonClicked	Bot API 7.10+ Occurs when the secondary button is pressed.
eventHandler receives no parameters.
backButtonClicked	Bot API 6.1+ Occurrs when the back button is pressed.
eventHandler receives no parameters.
settingsButtonClicked	Bot API 6.1+ Occurrs when the Settings item in context menu is pressed.
eventHandler receives no parameters.
invoiceClosed	Bot API 6.1+ Occurrs when the opened invoice is closed.
eventHandler receives an object with the two fields: url – invoice link provided and status – one of the invoice statuses:
- paid – invoice was paid successfully,
- cancelled – user closed this invoice without paying,
- failed – user tried to pay, but the payment was failed,
- pending – the payment is still processing. The bot will receive a service message about a successful payment when the payment is successfully paid.
popupClosed	Bot API 6.2+ Occurrs when the opened popup is closed.
eventHandler receives an object with the single field button_id – the value of the field id of the pressed button. If no buttons were pressed, the field button_id will be null.
qrTextReceived	Bot API 6.4+ Occurs when the QR code scanner catches a code with text data.
eventHandler receives an object with the single field data containing text data from the QR code.
scanQrPopupClosed	Bot API 7.7+ Occurs when the QR code scanner popup is closed by the user.
eventHandler receives no parameters.
clipboardTextReceived	Bot API 6.4+ Occurrs when the readTextFromClipboard method is called.
eventHandler receives an object with the single field data containing text data from the clipboard. If the clipboard contains non-text data, the field data will be an empty string. If the Mini App has no access to the clipboard, the field data will be null.
writeAccessRequested	Bot API 6.9+ Occurs when the write permission was requested.
eventHandler receives an object with the single field status containing one of the statuses:
- allowed – user granted write permission to the bot,
- cancelled – user declined this request.
contactRequested	Bot API 6.9+ Occurrs when the user's phone number was requested.
eventHandler receives an object with the single field status containing one of the statuses:
- sent – user shared their phone number with the bot,
- cancelled – user declined this request.
biometricManagerUpdated	Bot API 7.2+ Occurs whenever BiometricManager object is changed.
eventHandler receives no parameters.
biometricAuthRequested	Bot API 7.2+ Occurs whenever biometric authentication was requested.
eventHandler receives an object with the field isAuthenticated containing a boolean indicating whether the user was authenticated successfully. If isAuthenticated is true, the field biometricToken will contain the biometric token stored in secure storage on the device.
biometricTokenUpdated	Bot API 7.2+ Occurs whenever the biometric token was updated.
eventHandler receives an object with the single field isUpdated, containing a boolean indicating whether the token was updated.
fullscreenChanged NEW	Bot API 8.0+ Occurs whenever the Mini App enters or exits fullscreen mode.
eventHandler receives no parameters. The current fullscreen state can be checked via this.isFullscreen.
fullscreenFailed NEW	Bot API 8.0+ Occurs if a request to enter fullscreen mode fails.
eventHandler receives an object with the single field error, describing the reason for the failure. Possible values for error are:
UNSUPPORTED – Fullscreen mode is not supported on this device or platform.
ALREADY_FULLSCREEN – The Mini App is already in fullscreen mode.
homeScreenAdded NEW	Bot API 8.0+ Occurs when the Mini App is successfully added to the home screen.
eventHandler receives no parameters.
homeScreenChecked NEW	Bot API 8.0+ Occurs after checking the home screen status.
eventHandler receives an object with the field status, which is a string indicating the current home screen status. Possible values for status are:
- unsupported – the feature is not supported, and it is not possible to add the icon to the home screen,
- unknown – the feature is supported, and the icon can be added, but it is not possible to determine if the icon has already been added,
- added – the icon has already been added to the home screen,
- missed – the icon has not been added to the home screen.
accelerometerStarted NEW	Bot API 8.0+ Occurs when accelerometer tracking has started successfully.
eventHandler receives no parameters.
accelerometerStopped NEW	Bot API 8.0+ Occurs when accelerometer tracking has stopped.
eventHandler receives no parameters.
accelerometerChanged NEW	Bot API 8.0+ Occurs with the specified frequency after calling the start method, sending the current accelerometer data.
eventHandler receives no parameters, the current acceleration values can be received via this.x, this.y and this.z respectively.
accelerometerFailed NEW	Bot API 8.0+ Occurs if a request to start accelerometer tracking fails.
eventHandler receives an object with the single field error, describing the reason for the failure. Possible values for error are:
UNSUPPORTED – Accelerometer tracking is not supported on this device or platform.
deviceOrientationStarted NEW	Bot API 8.0+ Occurs when device orientation tracking has started successfully.
eventHandler receives no parameters.
deviceOrientationStopped NEW	Bot API 8.0+ Occurs when device orientation tracking has stopped.
eventHandler receives no parameters.
deviceOrientationChanged NEW	Bot API 8.0+ Occurs with the specified frequency after calling the start method, sending the current orientation data.
eventHandler receives no parameters, the current device orientation values can be received via this.alpha, this.beta and this.gamma respectively.
deviceOrientationFailed NEW	Bot API 8.0+ Occurs if a request to start device orientation tracking fails.
eventHandler receives an object with the single field error, describing the reason for the failure. Possible values for error are:
UNSUPPORTED – Device orientation tracking is not supported on this device or platform.
gyroscopeStarted NEW	Bot API 8.0+ Occurs when gyroscope tracking has started successfully.
eventHandler receives no parameters.
gyroscopeStopped NEW	Bot API 8.0+ Occurs when gyroscope tracking has stopped.
eventHandler receives no parameters.
gyroscopeChanged NEW	Bot API 8.0+ Occurs with the specified frequency after calling the start method, sending the current gyroscope data.
eventHandler receives no parameters, the current rotation rates can be received via this.x, this.y and this.z respectively.
gyroscopeFailed NEW	Bot API 8.0+ Occurs if a request to start gyroscope tracking fails.
eventHandler receives an object with the single field error, describing the reason for the failure. Possible values for error are:
UNSUPPORTED – Gyroscope tracking is not supported on this device or platform.
locationManagerUpdated NEW	Bot API 8.0+ Occurs whenever LocationManager object is changed.
eventHandler receives no parameters.
locationRequested NEW	Bot API 8.0+ Occurs when location data is requested.
eventHandler receives an object with the single field locationData of type LocationData, containing the current location information.
shareMessageSent NEW	Bot API 8.0+ Occurs when the message is successfully shared by the user.
eventHandler receives no parameters.
shareMessageFailed NEW	Bot API 8.0+ Occurs if sharing the message fails.
eventHandler receives an object with the single field error, describing the reason for the failure. Possible values for error are:
UNSUPPORTED – The feature is not supported by the client.
MESSAGE_EXPIRED – The message could not be retrieved because it has expired.
MESSAGE_SEND_FAILED – An error occurred while attempting to send the message.
USER_DECLINED – The user closed the dialog without sharing the message.
UNKNOWN_ERROR – An unknown error occurred.
emojiStatusSet NEW	Bot API 8.0+ Occurs when the emoji status is successfully set.
eventHandler receives no parameters.
emojiStatusFailed NEW	Bot API 8.0+ Occurs if setting the emoji status fails.
eventHandler receives an object with the single field error, describing the reason for the failure. Possible values for error are:
UNSUPPORTED – The feature is not supported by the client.
SUGGESTED_EMOJI_INVALID – One or more emoji identifiers are invalid.
DURATION_INVALID – The specified duration is invalid.
USER_DECLINED – The user closed the dialog without setting a status.
SERVER_ERROR – A server error occurred when attempting to set the status.
UNKNOWN_ERROR – An unknown error occurred.
emojiStatusAccessRequested NEW	Bot API 8.0+ Occurs when the write permission was requested.
eventHandler receives an object with the single field status containing one of the statuses:
- allowed – user granted emoji status permission to the bot,
- cancelled – user declined this request.
fileDownloadRequested NEW	Bot API 8.0+ Occurs when the user responds to the file download request.
eventHandler receives an object with the single field status containing one of the statuses:
- downloading – the file download has started,
- cancelled – user declined this request.
Adding Bots to the Attachment Menu
Attachment menu integration is currently only available for major advertisers on the Telegram Ad Platform. However, all bots can use it in the test server environment. Talk to Botfather on the test server to set up the integration.

A special link is used to add bots to the attachment menu:

https://t.me/botusername?startattach
or
https://t.me/botusername?startattach=command

For example, open this attachment menu link for @DurgerKingBot, then use the Attach menu in any private chat.

Opening the link prompts the user to add the bot to their attachment menu. If the bot has already been added, the attachment menu will open in the current chat and redirect to the bot there (if the link is opened from a 1-on-1 chat). If a non-empty startattach parameter was included in the link, it will be passed to the Mini App in the start_param field and in the GET parameter tgWebAppStartParam.

The following link formats are also supported:

https://t.me/username?attach=botusername
https://t.me/username?attach=botusername&startattach=command
https://t.me/+1234567890?attach=botusername
https://t.me/+1234567890?attach=botusername&startattach=command

These links open the Mini App in the attachment menu in the chat with a specific user. If the bot wasn't already added to the attachment menu, the user will be prompted to do so. If a non-empty startattach parameter was included in the link, it will be passed to the Mini App in the start_param field and in the GET parameter tgWebAppStartParam.

Bot API 6.1+ supports a new link format:

https://t.me/botusername?startattach&choose=users+bots
https://t.me/botusername?startattach=command&choose=groups+channels

Opening such a link prompts the user to choose a specific chat and opens the attachment menu in that chat. If the bot wasn't already added to the attachment menu, the user will be prompted to do so. You can specify which types of chats the user will be able to choose from. It can be one or more of the following types: users, bots, groups, channels separated by a + sign. If a non-empty startattach parameter was included in the link, it will be passed to the Mini App in the start_param field and in the GET parameter tgWebAppStartParam.

Additional Data in User-Agent
When the Mini App is running on Android, additional information is appended to the User-Agent string to provide more context about the app environment. This information includes the app version, device model, Android version, SDK version, and device performance class, formatted as follows:

Telegram-Android/{app_version} ({manufacturer} {model}; Android {android_version}; SDK {sdk_version}; {performance_class})
where:

{app_version} is the version of the Telegram app (e.g., 11.3.3),
{manufacturer} {model} represents the device’s manufacturer and model (e.g., Google sdk_gphone64_arm64),
{android_version} is the Android OS version running on the device (e.g., 14),
{sdk_version} indicates the Android SDK version (e.g., 34),
{performance_class} specifies the device performance class as LOW, AVERAGE, or HIGH, indicating the device's performance capacity.
Example
Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672.136 Mobile Safari/537.36 Telegram-Android/11.3.3 (Google sdk_gphone64_arm64; Android 14; SDK 34; LOW)

We recommend using this information to optimize your Mini App based on the device's capabilities. For instance, you can adjust animations and visual effects in games on low-performance devices to ensure a smooth experience for all users, regardless of device specifications.

Testing Mini Apps
Using bots in the test environment
To log in to the test environment, use either of the following:

iOS: tap 10 times on the Settings icon > Accounts > Login to another account > Test.
Telegram Desktop: open ☰ Settings > Shift + Alt + Right click ‘Add Account’ and select ‘Test Server’.
macOS: click the Settings icon 10 times to open the Debug Menu, ⌘ + click ‘Add Account’ and log in via phone number.
The test environment is completely separate from the main environment, so you will need to create a new user account and a new bot with @BotFather.

After receiving your bot token, you can send requests to the Bot API in this format:

https://api.telegram.org/bot<token>/test/METHOD_NAME
Note: When working with the test environment, you may use HTTP links without TLS to test your Mini App.

Debug Mode for Mini Apps
Use these tools to find app-specific issues in your Mini App:

iOS

In Telegram tap 10 times on the Settings icon and toggle on Allow Web View Inspection.
Connect your phone to your computer using a USB cable.
Open Safari on your Mac, then go to Develop > [Your Device Name] in the menu bar.
Launch your Mini App on the iOS device – it will appear in the Develop menu under your device.
Android

Enable USB-Debugging on your device.
In Telegram Settings, scroll all the way down, press and hold on the version number two times.
Choose Enable WebView Debug in the Debug Settings.
Connect your phone to your computer and open chrome://inspect/#devices in Chrome – you will see your Mini App there when you launch it on your phone.
Telegram Desktop on Windows and Linux

Download and launch the Beta Version of Telegram Desktop on Windows or Linux (not supported on Telegram Desktop for macOS yet).
Go to Settings > Advanced > Experimental settings > Enable webview inspection.
Right click in the WebView and choose Inspect.
Telegram macOS





 Twitter
Home
FAQ
Apps
API
Protocol
Schema
APISchema
Schema
Below you will find the current TL-schema. More details on TL »

See also the detailed schema in JSON »

See also TL-Schema for end-to-end encrypted messages »

Layer 214 
boolFalse#bc799737 = Bool;
boolTrue#997275b5 = Bool;

true#3fedd339 = True;

vector#1cb5c415 {t:Type} # [ t ] = Vector t;

error#c4b9f9bb code:int text:string = Error;

null#56730bcc = Null;

inputPeerEmpty#7f3b18ea = InputPeer;
inputPeerSelf#7da07ec9 = InputPeer;
inputPeerChat#35a95cb9 chat_id:long = InputPeer;
inputPeerUser#dde8a54c user_id:long access_hash:long = InputPeer;
inputPeerChannel#27bcbbfc channel_id:long access_hash:long = InputPeer;
inputPeerUserFromMessage#a87b0a1c peer:InputPeer msg_id:int user_id:long = InputPeer;
inputPeerChannelFromMessage#bd2a0840 peer:InputPeer msg_id:int channel_id:long = InputPeer;

inputUserEmpty#b98886cf = InputUser;
inputUserSelf#f7c1b13f = InputUser;
inputUser#f21158c6 user_id:long access_hash:long = InputUser;
inputUserFromMessage#1da448e2 peer:InputPeer msg_id:int user_id:long = InputUser;

inputPhoneContact#f392b7f4 client_id:long phone:string first_name:string last_name:string = InputContact;

inputFile#f52ff27f id:long parts:int name:string md5_checksum:string = InputFile;
inputFileBig#fa4f0bb5 id:long parts:int name:string = InputFile;
inputFileStoryDocument#62dc8b48 id:InputDocument = InputFile;

inputMediaEmpty#9664f57f = InputMedia;
inputMediaUploadedPhoto#1e287d04 flags:# spoiler:flags.2?true file:InputFile stickers:flags.0?Vector<InputDocument> ttl_seconds:flags.1?int = InputMedia;
inputMediaPhoto#b3ba0635 flags:# spoiler:flags.1?true id:InputPhoto ttl_seconds:flags.0?int = InputMedia;
inputMediaGeoPoint#f9c44144 geo_point:InputGeoPoint = InputMedia;
inputMediaContact#f8ab7dfb phone_number:string first_name:string last_name:string vcard:string = InputMedia;
inputMediaUploadedDocument#37c9330 flags:# nosound_video:flags.3?true force_file:flags.4?true spoiler:flags.5?true file:InputFile thumb:flags.2?InputFile mime_type:string attributes:Vector<DocumentAttribute> stickers:flags.0?Vector<InputDocument> video_cover:flags.6?InputPhoto video_timestamp:flags.7?int ttl_seconds:flags.1?int = InputMedia;
inputMediaDocument#a8763ab5 flags:# spoiler:flags.2?true id:InputDocument video_cover:flags.3?InputPhoto video_timestamp:flags.4?int ttl_seconds:flags.0?int query:flags.1?string = InputMedia;
inputMediaVenue#c13d1c11 geo_point:InputGeoPoint title:string address:string provider:string venue_id:string venue_type:string = InputMedia;
inputMediaPhotoExternal#e5bbfe1a flags:# spoiler:flags.1?true url:string ttl_seconds:flags.0?int = InputMedia;
inputMediaDocumentExternal#779600f9 flags:# spoiler:flags.1?true url:string ttl_seconds:flags.0?int video_cover:flags.2?InputPhoto video_timestamp:flags.3?int = InputMedia;
inputMediaGame#d33f43f3 id:InputGame = InputMedia;
inputMediaInvoice#405fef0d flags:# title:string description:string photo:flags.0?InputWebDocument invoice:Invoice payload:bytes provider:flags.3?string provider_data:DataJSON start_param:flags.1?string extended_media:flags.2?InputMedia = InputMedia;
inputMediaGeoLive#971fa843 flags:# stopped:flags.0?true geo_point:InputGeoPoint heading:flags.2?int period:flags.1?int proximity_notification_radius:flags.3?int = InputMedia;
inputMediaPoll#f94e5f1 flags:# poll:Poll correct_answers:flags.0?Vector<bytes> solution:flags.1?string solution_entities:flags.1?Vector<MessageEntity> = InputMedia;
inputMediaDice#e66fbf7b emoticon:string = InputMedia;
inputMediaStory#89fdd778 peer:InputPeer id:int = InputMedia;
inputMediaWebPage#c21b8849 flags:# force_large_media:flags.0?true force_small_media:flags.1?true optional:flags.2?true url:string = InputMedia;
inputMediaPaidMedia#c4103386 flags:# stars_amount:long extended_media:Vector<InputMedia> payload:flags.0?string = InputMedia;
inputMediaTodo#9fc55fde todo:TodoList = InputMedia;

inputChatPhotoEmpty#1ca48f57 = InputChatPhoto;
inputChatUploadedPhoto#bdcdaec0 flags:# file:flags.0?InputFile video:flags.1?InputFile video_start_ts:flags.2?double video_emoji_markup:flags.3?VideoSize = InputChatPhoto;
inputChatPhoto#8953ad37 id:InputPhoto = InputChatPhoto;

inputGeoPointEmpty#e4c123d6 = InputGeoPoint;
inputGeoPoint#48222faf flags:# lat:double long:double accuracy_radius:flags.0?int = InputGeoPoint;

inputPhotoEmpty#1cd7bf0d = InputPhoto;
inputPhoto#3bb3b94a id:long access_hash:long file_reference:bytes = InputPhoto;

inputFileLocation#dfdaabe1 volume_id:long local_id:int secret:long file_reference:bytes = InputFileLocation;
inputEncryptedFileLocation#f5235d55 id:long access_hash:long = InputFileLocation;
inputDocumentFileLocation#bad07584 id:long access_hash:long file_reference:bytes thumb_size:string = InputFileLocation;
inputSecureFileLocation#cbc7ee28 id:long access_hash:long = InputFileLocation;
inputTakeoutFileLocation#29be5899 = InputFileLocation;
inputPhotoFileLocation#40181ffe id:long access_hash:long file_reference:bytes thumb_size:string = InputFileLocation;
inputPhotoLegacyFileLocation#d83466f3 id:long access_hash:long file_reference:bytes volume_id:long local_id:int secret:long = InputFileLocation;
inputPeerPhotoFileLocation#37257e99 flags:# big:flags.0?true peer:InputPeer photo_id:long = InputFileLocation;
inputStickerSetThumb#9d84f3db stickerset:InputStickerSet thumb_version:int = InputFileLocation;
inputGroupCallStream#598a92a flags:# call:InputGroupCall time_ms:long scale:int video_channel:flags.0?int video_quality:flags.0?int = InputFileLocation;

peerUser#59511722 user_id:long = Peer;
peerChat#36c6019a chat_id:long = Peer;
peerChannel#a2a5371e channel_id:long = Peer;

storage.fileUnknown#aa963b05 = storage.FileType;
storage.filePartial#40bc6f52 = storage.FileType;
storage.fileJpeg#7efe0e = storage.FileType;
storage.fileGif#cae1aadf = storage.FileType;
storage.filePng#a4f63c0 = storage.FileType;
storage.filePdf#ae1e508d = storage.FileType;
storage.fileMp3#528a0677 = storage.FileType;
storage.fileMov#4b09ebbc = storage.FileType;
storage.fileMp4#b3cea0e4 = storage.FileType;
storage.fileWebp#1081464c = storage.FileType;

userEmpty#d3bc4b7a id:long = User;
user#20b1422 flags:# self:flags.10?true contact:flags.11?true mutual_contact:flags.12?true deleted:flags.13?true bot:flags.14?true bot_chat_history:flags.15?true bot_nochats:flags.16?true verified:flags.17?true restricted:flags.18?true min:flags.20?true bot_inline_geo:flags.21?true support:flags.23?true scam:flags.24?true apply_min_photo:flags.25?true fake:flags.26?true bot_attach_menu:flags.27?true premium:flags.28?true attach_menu_enabled:flags.29?true flags2:# bot_can_edit:flags2.1?true close_friend:flags2.2?true stories_hidden:flags2.3?true stories_unavailable:flags2.4?true contact_require_premium:flags2.10?true bot_business:flags2.11?true bot_has_main_app:flags2.13?true id:long access_hash:flags.0?long first_name:flags.1?string last_name:flags.2?string username:flags.3?string phone:flags.4?string photo:flags.5?UserProfilePhoto status:flags.6?UserStatus bot_info_version:flags.14?int restriction_reason:flags.18?Vector<RestrictionReason> bot_inline_placeholder:flags.19?string lang_code:flags.22?string emoji_status:flags.30?EmojiStatus usernames:flags2.0?Vector<Username> stories_max_id:flags2.5?int color:flags2.8?PeerColor profile_color:flags2.9?PeerColor bot_active_users:flags2.12?int bot_verification_icon:flags2.14?long send_paid_messages_stars:flags2.15?long = User;

userProfilePhotoEmpty#4f11bae1 = UserProfilePhoto;
userProfilePhoto#82d1f706 flags:# has_video:flags.0?true personal:flags.2?true photo_id:long stripped_thumb:flags.1?bytes dc_id:int = UserProfilePhoto;

userStatusEmpty#9d05049 = UserStatus;
userStatusOnline#edb93949 expires:int = UserStatus;
userStatusOffline#8c703f was_online:int = UserStatus;
userStatusRecently#7b197dc8 flags:# by_me:flags.0?true = UserStatus;
userStatusLastWeek#541a1d1a flags:# by_me:flags.0?true = UserStatus;
userStatusLastMonth#65899777 flags:# by_me:flags.0?true = UserStatus;

chatEmpty#29562865 id:long = Chat;
chat#41cbf256 flags:# creator:flags.0?true left:flags.2?true deactivated:flags.5?true call_active:flags.23?true call_not_empty:flags.24?true noforwards:flags.25?true id:long title:string photo:ChatPhoto participants_count:int date:int version:int migrated_to:flags.6?InputChannel admin_rights:flags.14?ChatAdminRights default_banned_rights:flags.18?ChatBannedRights = Chat;
chatForbidden#6592a1a7 id:long title:string = Chat;
channel#fe685355 flags:# creator:flags.0?true left:flags.2?true broadcast:flags.5?true verified:flags.7?true megagroup:flags.8?true restricted:flags.9?true signatures:flags.11?true min:flags.12?true scam:flags.19?true has_link:flags.20?true has_geo:flags.21?true slowmode_enabled:flags.22?true call_active:flags.23?true call_not_empty:flags.24?true fake:flags.25?true gigagroup:flags.26?true noforwards:flags.27?true join_to_send:flags.28?true join_request:flags.29?true forum:flags.30?true flags2:# stories_hidden:flags2.1?true stories_hidden_min:flags2.2?true stories_unavailable:flags2.3?true signature_profiles:flags2.12?true autotranslation:flags2.15?true broadcast_messages_allowed:flags2.16?true monoforum:flags2.17?true forum_tabs:flags2.19?true id:long access_hash:flags.13?long title:string username:flags.6?string photo:ChatPhoto date:int restriction_reason:flags.9?Vector<RestrictionReason> admin_rights:flags.14?ChatAdminRights banned_rights:flags.15?ChatBannedRights default_banned_rights:flags.18?ChatBannedRights participants_count:flags.17?int usernames:flags2.0?Vector<Username> stories_max_id:flags2.4?int color:flags2.7?PeerColor profile_color:flags2.8?PeerColor emoji_status:flags2.9?EmojiStatus level:flags2.10?int subscription_until_date:flags2.11?int bot_verification_icon:flags2.13?long send_paid_messages_stars:flags2.14?long linked_monoforum_id:flags2.18?long = Chat;
channelForbidden#17d493d5 flags:# broadcast:flags.5?true megagroup:flags.8?true id:long access_hash:long title:string until_date:flags.16?int = Chat;

chatFull#2633421b flags:# can_set_username:flags.7?true has_scheduled:flags.8?true translations_disabled:flags.19?true id:long about:string participants:ChatParticipants chat_photo:flags.2?Photo notify_settings:PeerNotifySettings exported_invite:flags.13?ExportedChatInvite bot_info:flags.3?Vector<BotInfo> pinned_msg_id:flags.6?int folder_id:flags.11?int call:flags.12?InputGroupCall ttl_period:flags.14?int groupcall_default_join_as:flags.15?Peer theme_emoticon:flags.16?string requests_pending:flags.17?int recent_requesters:flags.17?Vector<long> available_reactions:flags.18?ChatReactions reactions_limit:flags.20?int = ChatFull;
channelFull#e4e0b29d flags:# can_view_participants:flags.3?true can_set_username:flags.6?true can_set_stickers:flags.7?true hidden_prehistory:flags.10?true can_set_location:flags.16?true has_scheduled:flags.19?true can_view_stats:flags.20?true blocked:flags.22?true flags2:# can_delete_channel:flags2.0?true antispam:flags2.1?true participants_hidden:flags2.2?true translations_disabled:flags2.3?true stories_pinned_available:flags2.5?true view_forum_as_messages:flags2.6?true restricted_sponsored:flags2.11?true can_view_revenue:flags2.12?true paid_media_allowed:flags2.14?true can_view_stars_revenue:flags2.15?true paid_reactions_available:flags2.16?true stargifts_available:flags2.19?true paid_messages_available:flags2.20?true id:long about:string participants_count:flags.0?int admins_count:flags.1?int kicked_count:flags.2?int banned_count:flags.2?int online_count:flags.13?int read_inbox_max_id:int read_outbox_max_id:int unread_count:int chat_photo:Photo notify_settings:PeerNotifySettings exported_invite:flags.23?ExportedChatInvite bot_info:Vector<BotInfo> migrated_from_chat_id:flags.4?long migrated_from_max_id:flags.4?int pinned_msg_id:flags.5?int stickerset:flags.8?StickerSet available_min_id:flags.9?int folder_id:flags.11?int linked_chat_id:flags.14?long location:flags.15?ChannelLocation slowmode_seconds:flags.17?int slowmode_next_send_date:flags.18?int stats_dc:flags.12?int pts:int call:flags.21?InputGroupCall ttl_period:flags.24?int pending_suggestions:flags.25?Vector<string> groupcall_default_join_as:flags.26?Peer theme_emoticon:flags.27?string requests_pending:flags.28?int recent_requesters:flags.28?Vector<long> default_send_as:flags.29?Peer available_reactions:flags.30?ChatReactions reactions_limit:flags2.13?int stories:flags2.4?PeerStories wallpaper:flags2.7?WallPaper boosts_applied:flags2.8?int boosts_unrestrict:flags2.9?int emojiset:flags2.10?StickerSet bot_verification:flags2.17?BotVerification stargifts_count:flags2.18?int send_paid_messages_stars:flags2.21?long main_tab:flags2.22?ProfileTab = ChatFull;

chatParticipant#c02d4007 user_id:long inviter_id:long date:int = ChatParticipant;
chatParticipantCreator#e46bcee4 user_id:long = ChatParticipant;
chatParticipantAdmin#a0933f5b user_id:long inviter_id:long date:int = ChatParticipant;

chatParticipantsForbidden#8763d3e1 flags:# chat_id:long self_participant:flags.0?ChatParticipant = ChatParticipants;
chatParticipants#3cbc93f8 chat_id:long participants:Vector<ChatParticipant> version:int = ChatParticipants;

chatPhotoEmpty#37c1011c = ChatPhoto;
chatPhoto#1c6e1c11 flags:# has_video:flags.0?true photo_id:long stripped_thumb:flags.1?bytes dc_id:int = ChatPhoto;

messageEmpty#90a6ca84 flags:# id:int peer_id:flags.0?Peer = Message;
message#9815cec8 flags:# out:flags.1?true mentioned:flags.4?true media_unread:flags.5?true silent:flags.13?true post:flags.14?true from_scheduled:flags.18?true legacy:flags.19?true edit_hide:flags.21?true pinned:flags.24?true noforwards:flags.26?true invert_media:flags.27?true flags2:# offline:flags2.1?true video_processing_pending:flags2.4?true paid_suggested_post_stars:flags2.8?true paid_suggested_post_ton:flags2.9?true id:int from_id:flags.8?Peer from_boosts_applied:flags.29?int peer_id:Peer saved_peer_id:flags.28?Peer fwd_from:flags.2?MessageFwdHeader via_bot_id:flags.11?long via_business_bot_id:flags2.0?long reply_to:flags.3?MessageReplyHeader date:int message:string media:flags.9?MessageMedia reply_markup:flags.6?ReplyMarkup entities:flags.7?Vector<MessageEntity> views:flags.10?int forwards:flags.10?int replies:flags.23?MessageReplies edit_date:flags.15?int post_author:flags.16?string grouped_id:flags.17?long reactions:flags.20?MessageReactions restriction_reason:flags.22?Vector<RestrictionReason> ttl_period:flags.25?int quick_reply_shortcut_id:flags.30?int effect:flags2.2?long factcheck:flags2.3?FactCheck report_delivery_until_date:flags2.5?int paid_message_stars:flags2.6?long suggested_post:flags2.7?SuggestedPost = Message;
messageService#7a800e0a flags:# out:flags.1?true mentioned:flags.4?true media_unread:flags.5?true reactions_are_possible:flags.9?true silent:flags.13?true post:flags.14?true legacy:flags.19?true id:int from_id:flags.8?Peer peer_id:Peer saved_peer_id:flags.28?Peer reply_to:flags.3?MessageReplyHeader date:int action:MessageAction reactions:flags.20?MessageReactions ttl_period:flags.25?int = Message;

messageMediaEmpty#3ded6320 = MessageMedia;
messageMediaPhoto#695150d7 flags:# spoiler:flags.3?true photo:flags.0?Photo ttl_seconds:flags.2?int = MessageMedia;
messageMediaGeo#56e0d474 geo:GeoPoint = MessageMedia;
messageMediaContact#70322949 phone_number:string first_name:string last_name:string vcard:string user_id:long = MessageMedia;
messageMediaUnsupported#9f84f49e = MessageMedia;
messageMediaDocument#52d8ccd9 flags:# nopremium:flags.3?true spoiler:flags.4?true video:flags.6?true round:flags.7?true voice:flags.8?true document:flags.0?Document alt_documents:flags.5?Vector<Document> video_cover:flags.9?Photo video_timestamp:flags.10?int ttl_seconds:flags.2?int = MessageMedia;
messageMediaWebPage#ddf10c3b flags:# force_large_media:flags.0?true force_small_media:flags.1?true manual:flags.3?true safe:flags.4?true webpage:WebPage = MessageMedia;
messageMediaVenue#2ec0533f geo:GeoPoint title:string address:string provider:string venue_id:string venue_type:string = MessageMedia;
messageMediaGame#fdb19008 game:Game = MessageMedia;
messageMediaInvoice#f6a548d3 flags:# shipping_address_requested:flags.1?true test:flags.3?true title:string description:string photo:flags.0?WebDocument receipt_msg_id:flags.2?int currency:string total_amount:long start_param:string extended_media:flags.4?MessageExtendedMedia = MessageMedia;
messageMediaGeoLive#b940c666 flags:# geo:GeoPoint heading:flags.0?int period:int proximity_notification_radius:flags.1?int = MessageMedia;
messageMediaPoll#4bd6e798 poll:Poll results:PollResults = MessageMedia;
messageMediaDice#3f7ee58b value:int emoticon:string = MessageMedia;
messageMediaStory#68cb6283 flags:# via_mention:flags.1?true peer:Peer id:int story:flags.0?StoryItem = MessageMedia;
messageMediaGiveaway#aa073beb flags:# only_new_subscribers:flags.0?true winners_are_visible:flags.2?true channels:Vector<long> countries_iso2:flags.1?Vector<string> prize_description:flags.3?string quantity:int months:flags.4?int stars:flags.5?long until_date:int = MessageMedia;
messageMediaGiveawayResults#ceaa3ea1 flags:# only_new_subscribers:flags.0?true refunded:flags.2?true channel_id:long additional_peers_count:flags.3?int launch_msg_id:int winners_count:int unclaimed_count:int winners:Vector<long> months:flags.4?int stars:flags.5?long prize_description:flags.1?string until_date:int = MessageMedia;
messageMediaPaidMedia#a8852491 stars_amount:long extended_media:Vector<MessageExtendedMedia> = MessageMedia;
messageMediaToDo#8a53b014 flags:# todo:TodoList completions:flags.0?Vector<TodoCompletion> = MessageMedia;

messageActionEmpty#b6aef7b0 = MessageAction;
messageActionChatCreate#bd47cbad title:string users:Vector<long> = MessageAction;
messageActionChatEditTitle#b5a1ce5a title:string = MessageAction;
messageActionChatEditPhoto#7fcb13a8 photo:Photo = MessageAction;
messageActionChatDeletePhoto#95e3fbef = MessageAction;
messageActionChatAddUser#15cefd00 users:Vector<long> = MessageAction;
messageActionChatDeleteUser#a43f30cc user_id:long = MessageAction;
messageActionChatJoinedByLink#31224c3 inviter_id:long = MessageAction;
messageActionChannelCreate#95d2ac92 title:string = MessageAction;
messageActionChatMigrateTo#e1037f92 channel_id:long = MessageAction;
messageActionChannelMigrateFrom#ea3948e9 title:string chat_id:long = MessageAction;
messageActionPinMessage#94bd38ed = MessageAction;
messageActionHistoryClear#9fbab604 = MessageAction;
messageActionGameScore#92a72876 game_id:long score:int = MessageAction;
messageActionPaymentSentMe#ffa00ccc flags:# recurring_init:flags.2?true recurring_used:flags.3?true currency:string total_amount:long payload:bytes info:flags.0?PaymentRequestedInfo shipping_option_id:flags.1?string charge:PaymentCharge subscription_until_date:flags.4?int = MessageAction;
messageActionPaymentSent#c624b16e flags:# recurring_init:flags.2?true recurring_used:flags.3?true currency:string total_amount:long invoice_slug:flags.0?string subscription_until_date:flags.4?int = MessageAction;
messageActionPhoneCall#80e11a7f flags:# video:flags.2?true call_id:long reason:flags.0?PhoneCallDiscardReason duration:flags.1?int = MessageAction;
messageActionScreenshotTaken#4792929b = MessageAction;
messageActionCustomAction#fae69f56 message:string = MessageAction;
messageActionBotAllowed#c516d679 flags:# attach_menu:flags.1?true from_request:flags.3?true domain:flags.0?string app:flags.2?BotApp = MessageAction;
messageActionSecureValuesSentMe#1b287353 values:Vector<SecureValue> credentials:SecureCredentialsEncrypted = MessageAction;
messageActionSecureValuesSent#d95c6154 types:Vector<SecureValueType> = MessageAction;
messageActionContactSignUp#f3f25f76 = MessageAction;
messageActionGeoProximityReached#98e0d697 from_id:Peer to_id:Peer distance:int = MessageAction;
messageActionGroupCall#7a0d7f42 flags:# call:InputGroupCall duration:flags.0?int = MessageAction;
messageActionInviteToGroupCall#502f92f7 call:InputGroupCall users:Vector<long> = MessageAction;
messageActionSetMessagesTTL#3c134d7b flags:# period:int auto_setting_from:flags.0?long = MessageAction;
messageActionGroupCallScheduled#b3a07661 call:InputGroupCall schedule_date:int = MessageAction;
messageActionSetChatTheme#b91bbd3a theme:ChatTheme = MessageAction;
messageActionChatJoinedByRequest#ebbca3cb = MessageAction;
messageActionWebViewDataSentMe#47dd8079 text:string data:string = MessageAction;
messageActionWebViewDataSent#b4c38cb5 text:string = MessageAction;
messageActionGiftPremium#6c6274fa flags:# currency:string amount:long months:int crypto_currency:flags.0?string crypto_amount:flags.0?long message:flags.1?TextWithEntities = MessageAction;
messageActionTopicCreate#d999256 flags:# title:string icon_color:int icon_emoji_id:flags.0?long = MessageAction;
messageActionTopicEdit#c0944820 flags:# title:flags.0?string icon_emoji_id:flags.1?long closed:flags.2?Bool hidden:flags.3?Bool = MessageAction;
messageActionSuggestProfilePhoto#57de635e photo:Photo = MessageAction;
messageActionRequestedPeer#31518e9b button_id:int peers:Vector<Peer> = MessageAction;
messageActionSetChatWallPaper#5060a3f4 flags:# same:flags.0?true for_both:flags.1?true wallpaper:WallPaper = MessageAction;
messageActionGiftCode#56d03994 flags:# via_giveaway:flags.0?true unclaimed:flags.5?true boost_peer:flags.1?Peer months:int slug:string currency:flags.2?string amount:flags.2?long crypto_currency:flags.3?string crypto_amount:flags.3?long message:flags.4?TextWithEntities = MessageAction;
messageActionGiveawayLaunch#a80f51e4 flags:# stars:flags.0?long = MessageAction;
messageActionGiveawayResults#87e2f155 flags:# stars:flags.0?true winners_count:int unclaimed_count:int = MessageAction;
messageActionBoostApply#cc02aa6d boosts:int = MessageAction;
messageActionRequestedPeerSentMe#93b31848 button_id:int peers:Vector<RequestedPeer> = MessageAction;
messageActionPaymentRefunded#41b3e202 flags:# peer:Peer currency:string total_amount:long payload:flags.0?bytes charge:PaymentCharge = MessageAction;
messageActionGiftStars#45d5b021 flags:# currency:string amount:long stars:long crypto_currency:flags.0?string crypto_amount:flags.0?long transaction_id:flags.1?string = MessageAction;
messageActionPrizeStars#b00c47a2 flags:# unclaimed:flags.0?true stars:long transaction_id:string boost_peer:Peer giveaway_msg_id:int = MessageAction;
messageActionStarGift#f24de7fa flags:# name_hidden:flags.0?true saved:flags.2?true converted:flags.3?true upgraded:flags.5?true refunded:flags.9?true can_upgrade:flags.10?true prepaid_upgrade:flags.13?true upgrade_separate:flags.16?true gift:StarGift message:flags.1?TextWithEntities convert_stars:flags.4?long upgrade_msg_id:flags.5?int upgrade_stars:flags.8?long from_id:flags.11?Peer peer:flags.12?Peer saved_id:flags.12?long prepaid_upgrade_hash:flags.14?string gift_msg_id:flags.15?int = MessageAction;
messageActionStarGiftUnique#34f762f3 flags:# upgrade:flags.0?true transferred:flags.1?true saved:flags.2?true refunded:flags.5?true prepaid_upgrade:flags.11?true gift:StarGift can_export_at:flags.3?int transfer_stars:flags.4?long from_id:flags.6?Peer peer:flags.7?Peer saved_id:flags.7?long resale_amount:flags.8?StarsAmount can_transfer_at:flags.9?int can_resell_at:flags.10?int = MessageAction;
messageActionPaidMessagesRefunded#ac1f1fcd count:int stars:long = MessageAction;
messageActionPaidMessagesPrice#84b88578 flags:# broadcast_messages_allowed:flags.0?true stars:long = MessageAction;
messageActionConferenceCall#2ffe2f7a flags:# missed:flags.0?true active:flags.1?true video:flags.4?true call_id:long duration:flags.2?int other_participants:flags.3?Vector<Peer> = MessageAction;
messageActionTodoCompletions#cc7c5c89 completed:Vector<int> incompleted:Vector<int> = MessageAction;
messageActionTodoAppendTasks#c7edbc83 list:Vector<TodoItem> = MessageAction;
messageActionSuggestedPostApproval#ee7a1596 flags:# rejected:flags.0?true balance_too_low:flags.1?true reject_comment:flags.2?string schedule_date:flags.3?int price:flags.4?StarsAmount = MessageAction;
messageActionSuggestedPostSuccess#95ddcf69 price:StarsAmount = MessageAction;
messageActionSuggestedPostRefund#69f916f8 flags:# payer_initiated:flags.0?true = MessageAction;
messageActionGiftTon#a8a3c699 flags:# currency:string amount:long crypto_currency:string crypto_amount:long transaction_id:flags.0?string = MessageAction;

dialog#d58a08c6 flags:# pinned:flags.2?true unread_mark:flags.3?true view_forum_as_messages:flags.6?true peer:Peer top_message:int read_inbox_max_id:int read_outbox_max_id:int unread_count:int unread_mentions_count:int unread_reactions_count:int notify_settings:PeerNotifySettings pts:flags.0?int draft:flags.1?DraftMessage folder_id:flags.4?int ttl_period:flags.5?int = Dialog;
dialogFolder#71bd134c flags:# pinned:flags.2?true folder:Folder peer:Peer top_message:int unread_muted_peers_count:int unread_unmuted_peers_count:int unread_muted_messages_count:int unread_unmuted_messages_count:int = Dialog;

photoEmpty#2331b22d id:long = Photo;
photo#fb197a65 flags:# has_stickers:flags.0?true id:long access_hash:long file_reference:bytes date:int sizes:Vector<PhotoSize> video_sizes:flags.1?Vector<VideoSize> dc_id:int = Photo;

photoSizeEmpty#e17e23c type:string = PhotoSize;
photoSize#75c78e60 type:string w:int h:int size:int = PhotoSize;
photoCachedSize#21e1ad6 type:string w:int h:int bytes:bytes = PhotoSize;
photoStrippedSize#e0b0bc2e type:string bytes:bytes = PhotoSize;
photoSizeProgressive#fa3efb95 type:string w:int h:int sizes:Vector<int> = PhotoSize;
photoPathSize#d8214d41 type:string bytes:bytes = PhotoSize;

geoPointEmpty#1117dd5f = GeoPoint;
geoPoint#b2a2f663 flags:# long:double lat:double access_hash:long accuracy_radius:flags.0?int = GeoPoint;

auth.sentCode#5e002502 flags:# type:auth.SentCodeType phone_code_hash:string next_type:flags.1?auth.CodeType timeout:flags.2?int = auth.SentCode;
auth.sentCodeSuccess#2390fe44 authorization:auth.Authorization = auth.SentCode;
auth.sentCodePaymentRequired#d7a2fcf9 store_product:string phone_code_hash:string support_email_address:string support_email_subject:string = auth.SentCode;

auth.authorization#2ea2c0d4 flags:# setup_password_required:flags.1?true otherwise_relogin_days:flags.1?int tmp_sessions:flags.0?int future_auth_token:flags.2?bytes user:User = auth.Authorization;
auth.authorizationSignUpRequired#44747e9a flags:# terms_of_service:flags.0?help.TermsOfService = auth.Authorization;

auth.exportedAuthorization#b434e2b8 id:long bytes:bytes = auth.ExportedAuthorization;

inputNotifyPeer#b8bc5b0c peer:InputPeer = InputNotifyPeer;
inputNotifyUsers#193b4417 = InputNotifyPeer;
inputNotifyChats#4a95e84e = InputNotifyPeer;
inputNotifyBroadcasts#b1db7c7e = InputNotifyPeer;
inputNotifyForumTopic#5c467992 peer:InputPeer top_msg_id:int = InputNotifyPeer;

inputPeerNotifySettings#cacb6ae2 flags:# show_previews:flags.0?Bool silent:flags.1?Bool mute_until:flags.2?int sound:flags.3?NotificationSound stories_muted:flags.6?Bool stories_hide_sender:flags.7?Bool stories_sound:flags.8?NotificationSound = InputPeerNotifySettings;

peerNotifySettings#99622c0c flags:# show_previews:flags.0?Bool silent:flags.1?Bool mute_until:flags.2?int ios_sound:flags.3?NotificationSound android_sound:flags.4?NotificationSound other_sound:flags.5?NotificationSound stories_muted:flags.6?Bool stories_hide_sender:flags.7?Bool stories_ios_sound:flags.8?NotificationSound stories_android_sound:flags.9?NotificationSound stories_other_sound:flags.10?NotificationSound = PeerNotifySettings;

peerSettings#f47741f7 flags:# report_spam:flags.0?true add_contact:flags.1?true block_contact:flags.2?true share_contact:flags.3?true need_contacts_exception:flags.4?true report_geo:flags.5?true autoarchived:flags.7?true invite_members:flags.8?true request_chat_broadcast:flags.10?true business_bot_paused:flags.11?true business_bot_can_reply:flags.12?true geo_distance:flags.6?int request_chat_title:flags.9?string request_chat_date:flags.9?int business_bot_id:flags.13?long business_bot_manage_url:flags.13?string charge_paid_message_stars:flags.14?long registration_month:flags.15?string phone_country:flags.16?string name_change_date:flags.17?int photo_change_date:flags.18?int = PeerSettings;

wallPaper#a437c3ed id:long flags:# creator:flags.0?true default:flags.1?true pattern:flags.3?true dark:flags.4?true access_hash:long slug:string document:Document settings:flags.2?WallPaperSettings = WallPaper;
wallPaperNoFile#e0804116 id:long flags:# default:flags.1?true dark:flags.4?true settings:flags.2?WallPaperSettings = WallPaper;

inputReportReasonSpam#58dbcab8 = ReportReason;
inputReportReasonViolence#1e22c78d = ReportReason;
inputReportReasonPornography#2e59d922 = ReportReason;
inputReportReasonChildAbuse#adf44ee3 = ReportReason;
inputReportReasonOther#c1e4a2b1 = ReportReason;
inputReportReasonCopyright#9b89f93a = ReportReason;
inputReportReasonGeoIrrelevant#dbd4feed = ReportReason;
inputReportReasonFake#f5ddd6e7 = ReportReason;
inputReportReasonIllegalDrugs#a8eb2be = ReportReason;
inputReportReasonPersonalDetails#9ec7863d = ReportReason;

userFull#c577b5ad flags:# blocked:flags.0?true phone_calls_available:flags.4?true phone_calls_private:flags.5?true can_pin_message:flags.7?true has_scheduled:flags.12?true video_calls_available:flags.13?true voice_messages_forbidden:flags.20?true translations_disabled:flags.23?true stories_pinned_available:flags.26?true blocked_my_stories_from:flags.27?true wallpaper_overridden:flags.28?true contact_require_premium:flags.29?true read_dates_private:flags.30?true flags2:# sponsored_enabled:flags2.7?true can_view_revenue:flags2.9?true bot_can_manage_emoji_status:flags2.10?true display_gifts_button:flags2.16?true id:long about:flags.1?string settings:PeerSettings personal_photo:flags.21?Photo profile_photo:flags.2?Photo fallback_photo:flags.22?Photo notify_settings:PeerNotifySettings bot_info:flags.3?BotInfo pinned_msg_id:flags.6?int common_chats_count:int folder_id:flags.11?int ttl_period:flags.14?int theme:flags.15?ChatTheme private_forward_name:flags.16?string bot_group_admin_rights:flags.17?ChatAdminRights bot_broadcast_admin_rights:flags.18?ChatAdminRights wallpaper:flags.24?WallPaper stories:flags.25?PeerStories business_work_hours:flags2.0?BusinessWorkHours business_location:flags2.1?BusinessLocation business_greeting_message:flags2.2?BusinessGreetingMessage business_away_message:flags2.3?BusinessAwayMessage business_intro:flags2.4?BusinessIntro birthday:flags2.5?Birthday personal_channel_id:flags2.6?long personal_channel_message:flags2.6?int stargifts_count:flags2.8?int starref_program:flags2.11?StarRefProgram bot_verification:flags2.12?BotVerification send_paid_messages_stars:flags2.14?long disallowed_gifts:flags2.15?DisallowedGiftsSettings stars_rating:flags2.17?StarsRating stars_my_pending_rating:flags2.18?StarsRating stars_my_pending_rating_date:flags2.18?int main_tab:flags2.20?ProfileTab saved_music:flags2.21?Document = UserFull;

contact#145ade0b user_id:long mutual:Bool = Contact;

importedContact#c13e3c50 user_id:long client_id:long = ImportedContact;

contactStatus#16d9703b user_id:long status:UserStatus = ContactStatus;

contacts.contactsNotModified#b74ba9d2 = contacts.Contacts;
contacts.contacts#eae87e42 contacts:Vector<Contact> saved_count:int users:Vector<User> = contacts.Contacts;

contacts.importedContacts#77d01c3b imported:Vector<ImportedContact> popular_invites:Vector<PopularContact> retry_contacts:Vector<long> users:Vector<User> = contacts.ImportedContacts;

contacts.blocked#ade1591 blocked:Vector<PeerBlocked> chats:Vector<Chat> users:Vector<User> = contacts.Blocked;
contacts.blockedSlice#e1664194 count:int blocked:Vector<PeerBlocked> chats:Vector<Chat> users:Vector<User> = contacts.Blocked;

messages.dialogs#15ba6c40 dialogs:Vector<Dialog> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.Dialogs;
messages.dialogsSlice#71e094f3 count:int dialogs:Vector<Dialog> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.Dialogs;
messages.dialogsNotModified#f0e3e596 count:int = messages.Dialogs;

messages.messages#8c718e87 messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.Messages;
messages.messagesSlice#762b263d flags:# inexact:flags.1?true count:int next_rate:flags.0?int offset_id_offset:flags.2?int search_flood:flags.3?SearchPostsFlood messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.Messages;
messages.channelMessages#c776ba4e flags:# inexact:flags.1?true pts:int count:int offset_id_offset:flags.2?int messages:Vector<Message> topics:Vector<ForumTopic> chats:Vector<Chat> users:Vector<User> = messages.Messages;
messages.messagesNotModified#74535f21 count:int = messages.Messages;

messages.chats#64ff9fd5 chats:Vector<Chat> = messages.Chats;
messages.chatsSlice#9cd81144 count:int chats:Vector<Chat> = messages.Chats;

messages.chatFull#e5d7d19c full_chat:ChatFull chats:Vector<Chat> users:Vector<User> = messages.ChatFull;

messages.affectedHistory#b45c69d1 pts:int pts_count:int offset:int = messages.AffectedHistory;

inputMessagesFilterEmpty#57e2f66c = MessagesFilter;
inputMessagesFilterPhotos#9609a51c = MessagesFilter;
inputMessagesFilterVideo#9fc00e65 = MessagesFilter;
inputMessagesFilterPhotoVideo#56e9f0e4 = MessagesFilter;
inputMessagesFilterDocument#9eddf188 = MessagesFilter;
inputMessagesFilterUrl#7ef0dd87 = MessagesFilter;
inputMessagesFilterGif#ffc86587 = MessagesFilter;
inputMessagesFilterVoice#50f5c392 = MessagesFilter;
inputMessagesFilterMusic#3751b49e = MessagesFilter;
inputMessagesFilterChatPhotos#3a20ecb8 = MessagesFilter;
inputMessagesFilterPhoneCalls#80c99768 flags:# missed:flags.0?true = MessagesFilter;
inputMessagesFilterRoundVoice#7a7c17a4 = MessagesFilter;
inputMessagesFilterRoundVideo#b549da53 = MessagesFilter;
inputMessagesFilterMyMentions#c1f8e69a = MessagesFilter;
inputMessagesFilterGeo#e7026d0d = MessagesFilter;
inputMessagesFilterContacts#e062db83 = MessagesFilter;
inputMessagesFilterPinned#1bb00451 = MessagesFilter;

updateNewMessage#1f2b0afd message:Message pts:int pts_count:int = Update;
updateMessageID#4e90bfd6 id:int random_id:long = Update;
updateDeleteMessages#a20db0e5 messages:Vector<int> pts:int pts_count:int = Update;
updateUserTyping#c01e857f user_id:long action:SendMessageAction = Update;
updateChatUserTyping#83487af0 chat_id:long from_id:Peer action:SendMessageAction = Update;
updateChatParticipants#7761198 participants:ChatParticipants = Update;
updateUserStatus#e5bdf8de user_id:long status:UserStatus = Update;
updateUserName#a7848924 user_id:long first_name:string last_name:string usernames:Vector<Username> = Update;
updateNewAuthorization#8951abef flags:# unconfirmed:flags.0?true hash:long date:flags.0?int device:flags.0?string location:flags.0?string = Update;
updateNewEncryptedMessage#12bcbd9a message:EncryptedMessage qts:int = Update;
updateEncryptedChatTyping#1710f156 chat_id:int = Update;
updateEncryption#b4a2e88d chat:EncryptedChat date:int = Update;
updateEncryptedMessagesRead#38fe25b7 chat_id:int max_date:int date:int = Update;
updateChatParticipantAdd#3dda5451 chat_id:long user_id:long inviter_id:long date:int version:int = Update;
updateChatParticipantDelete#e32f3d77 chat_id:long user_id:long version:int = Update;
updateDcOptions#8e5e9873 dc_options:Vector<DcOption> = Update;
updateNotifySettings#bec268ef peer:NotifyPeer notify_settings:PeerNotifySettings = Update;
updateServiceNotification#ebe46819 flags:# popup:flags.0?true invert_media:flags.2?true inbox_date:flags.1?int type:string message:string media:MessageMedia entities:Vector<MessageEntity> = Update;
updatePrivacy#ee3b272a key:PrivacyKey rules:Vector<PrivacyRule> = Update;
updateUserPhone#5492a13 user_id:long phone:string = Update;
updateReadHistoryInbox#9c974fdf flags:# folder_id:flags.0?int peer:Peer max_id:int still_unread_count:int pts:int pts_count:int = Update;
updateReadHistoryOutbox#2f2f21bf peer:Peer max_id:int pts:int pts_count:int = Update;
updateWebPage#7f891213 webpage:WebPage pts:int pts_count:int = Update;
updateReadMessagesContents#f8227181 flags:# messages:Vector<int> pts:int pts_count:int date:flags.0?int = Update;
updateChannelTooLong#108d941f flags:# channel_id:long pts:flags.0?int = Update;
updateChannel#635b4c09 channel_id:long = Update;
updateNewChannelMessage#62ba04d9 message:Message pts:int pts_count:int = Update;
updateReadChannelInbox#922e6e10 flags:# folder_id:flags.0?int channel_id:long max_id:int still_unread_count:int pts:int = Update;
updateDeleteChannelMessages#c32d5b12 channel_id:long messages:Vector<int> pts:int pts_count:int = Update;
updateChannelMessageViews#f226ac08 channel_id:long id:int views:int = Update;
updateChatParticipantAdmin#d7ca61a2 chat_id:long user_id:long is_admin:Bool version:int = Update;
updateNewStickerSet#688a30aa stickerset:messages.StickerSet = Update;
updateStickerSetsOrder#bb2d201 flags:# masks:flags.0?true emojis:flags.1?true order:Vector<long> = Update;
updateStickerSets#31c24808 flags:# masks:flags.0?true emojis:flags.1?true = Update;
updateSavedGifs#9375341e = Update;
updateBotInlineQuery#496f379c flags:# query_id:long user_id:long query:string geo:flags.0?GeoPoint peer_type:flags.1?InlineQueryPeerType offset:string = Update;
updateBotInlineSend#12f12a07 flags:# user_id:long query:string geo:flags.0?GeoPoint id:string msg_id:flags.1?InputBotInlineMessageID = Update;
updateEditChannelMessage#1b3f4df7 message:Message pts:int pts_count:int = Update;
updateBotCallbackQuery#b9cfc48d flags:# query_id:long user_id:long peer:Peer msg_id:int chat_instance:long data:flags.0?bytes game_short_name:flags.1?string = Update;
updateEditMessage#e40370a3 message:Message pts:int pts_count:int = Update;
updateInlineBotCallbackQuery#691e9052 flags:# query_id:long user_id:long msg_id:InputBotInlineMessageID chat_instance:long data:flags.0?bytes game_short_name:flags.1?string = Update;
updateReadChannelOutbox#b75f99a9 channel_id:long max_id:int = Update;
updateDraftMessage#edfc111e flags:# peer:Peer top_msg_id:flags.0?int saved_peer_id:flags.1?Peer draft:DraftMessage = Update;
updateReadFeaturedStickers#571d2742 = Update;
updateRecentStickers#9a422c20 = Update;
updateConfig#a229dd06 = Update;
updatePtsChanged#3354678f = Update;
updateChannelWebPage#2f2ba99f channel_id:long webpage:WebPage pts:int pts_count:int = Update;
updateDialogPinned#6e6fe51c flags:# pinned:flags.0?true folder_id:flags.1?int peer:DialogPeer = Update;
updatePinnedDialogs#fa0f3ca2 flags:# folder_id:flags.1?int order:flags.0?Vector<DialogPeer> = Update;
updateBotWebhookJSON#8317c0c3 data:DataJSON = Update;
updateBotWebhookJSONQuery#9b9240a6 query_id:long data:DataJSON timeout:int = Update;
updateBotShippingQuery#b5aefd7d query_id:long user_id:long payload:bytes shipping_address:PostAddress = Update;
updateBotPrecheckoutQuery#8caa9a96 flags:# query_id:long user_id:long payload:bytes info:flags.0?PaymentRequestedInfo shipping_option_id:flags.1?string currency:string total_amount:long = Update;
updatePhoneCall#ab0f6b1e phone_call:PhoneCall = Update;
updateLangPackTooLong#46560264 lang_code:string = Update;
updateLangPack#56022f4d difference:LangPackDifference = Update;
updateFavedStickers#e511996d = Update;
updateChannelReadMessagesContents#25f324f7 flags:# channel_id:long top_msg_id:flags.0?int saved_peer_id:flags.1?Peer messages:Vector<int> = Update;
updateContactsReset#7084a7be = Update;
updateChannelAvailableMessages#b23fc698 channel_id:long available_min_id:int = Update;
updateDialogUnreadMark#b658f23e flags:# unread:flags.0?true peer:DialogPeer saved_peer_id:flags.1?Peer = Update;
updateMessagePoll#aca1657b flags:# poll_id:long poll:flags.0?Poll results:PollResults = Update;
updateChatDefaultBannedRights#54c01850 peer:Peer default_banned_rights:ChatBannedRights version:int = Update;
updateFolderPeers#19360dc0 folder_peers:Vector<FolderPeer> pts:int pts_count:int = Update;
updatePeerSettings#6a7e7366 peer:Peer settings:PeerSettings = Update;
updatePeerLocated#b4afcfb0 peers:Vector<PeerLocated> = Update;
updateNewScheduledMessage#39a51dfb message:Message = Update;
updateDeleteScheduledMessages#f2a71983 flags:# peer:Peer messages:Vector<int> sent_messages:flags.0?Vector<int> = Update;
updateTheme#8216fba3 theme:Theme = Update;
updateGeoLiveViewed#871fb939 peer:Peer msg_id:int = Update;
updateLoginToken#564fe691 = Update;
updateMessagePollVote#24f40e77 poll_id:long peer:Peer options:Vector<bytes> qts:int = Update;
updateDialogFilter#26ffde7d flags:# id:int filter:flags.0?DialogFilter = Update;
updateDialogFilterOrder#a5d72105 order:Vector<int> = Update;
updateDialogFilters#3504914f = Update;
updatePhoneCallSignalingData#2661bf09 phone_call_id:long data:bytes = Update;
updateChannelMessageForwards#d29a27f4 channel_id:long id:int forwards:int = Update;
updateReadChannelDiscussionInbox#d6b19546 flags:# channel_id:long top_msg_id:int read_max_id:int broadcast_id:flags.0?long broadcast_post:flags.0?int = Update;
updateReadChannelDiscussionOutbox#695c9e7c channel_id:long top_msg_id:int read_max_id:int = Update;
updatePeerBlocked#ebe07752 flags:# blocked:flags.0?true blocked_my_stories_from:flags.1?true peer_id:Peer = Update;
updateChannelUserTyping#8c88c923 flags:# channel_id:long top_msg_id:flags.0?int from_id:Peer action:SendMessageAction = Update;
updatePinnedMessages#ed85eab5 flags:# pinned:flags.0?true peer:Peer messages:Vector<int> pts:int pts_count:int = Update;
updatePinnedChannelMessages#5bb98608 flags:# pinned:flags.0?true channel_id:long messages:Vector<int> pts:int pts_count:int = Update;
updateChat#f89a6a4e chat_id:long = Update;
updateGroupCallParticipants#f2ebdb4e call:InputGroupCall participants:Vector<GroupCallParticipant> version:int = Update;
updateGroupCall#97d64341 flags:# chat_id:flags.0?long call:GroupCall = Update;
updatePeerHistoryTTL#bb9bb9a5 flags:# peer:Peer ttl_period:flags.0?int = Update;
updateChatParticipant#d087663a flags:# chat_id:long date:int actor_id:long user_id:long prev_participant:flags.0?ChatParticipant new_participant:flags.1?ChatParticipant invite:flags.2?ExportedChatInvite qts:int = Update;
updateChannelParticipant#985d3abb flags:# via_chatlist:flags.3?true channel_id:long date:int actor_id:long user_id:long prev_participant:flags.0?ChannelParticipant new_participant:flags.1?ChannelParticipant invite:flags.2?ExportedChatInvite qts:int = Update;
updateBotStopped#c4870a49 user_id:long date:int stopped:Bool qts:int = Update;
updateGroupCallConnection#b783982 flags:# presentation:flags.0?true params:DataJSON = Update;
updateBotCommands#4d712f2e peer:Peer bot_id:long commands:Vector<BotCommand> = Update;
updatePendingJoinRequests#7063c3db peer:Peer requests_pending:int recent_requesters:Vector<long> = Update;
updateBotChatInviteRequester#11dfa986 peer:Peer date:int user_id:long about:string invite:ExportedChatInvite qts:int = Update;
updateMessageReactions#1e297bfa flags:# peer:Peer msg_id:int top_msg_id:flags.0?int saved_peer_id:flags.1?Peer reactions:MessageReactions = Update;
updateAttachMenuBots#17b7a20b = Update;
updateWebViewResultSent#1592b79d query_id:long = Update;
updateBotMenuButton#14b85813 bot_id:long button:BotMenuButton = Update;
updateSavedRingtones#74d8be99 = Update;
updateTranscribedAudio#84cd5a flags:# pending:flags.0?true peer:Peer msg_id:int transcription_id:long text:string = Update;
updateReadFeaturedEmojiStickers#fb4c496c = Update;
updateUserEmojiStatus#28373599 user_id:long emoji_status:EmojiStatus = Update;
updateRecentEmojiStatuses#30f443db = Update;
updateRecentReactions#6f7863f4 = Update;
updateMoveStickerSetToTop#86fccf85 flags:# masks:flags.0?true emojis:flags.1?true stickerset:long = Update;
updateMessageExtendedMedia#d5a41724 peer:Peer msg_id:int extended_media:Vector<MessageExtendedMedia> = Update;
updateChannelPinnedTopic#192efbe3 flags:# pinned:flags.0?true channel_id:long topic_id:int = Update;
updateChannelPinnedTopics#fe198602 flags:# channel_id:long order:flags.0?Vector<int> = Update;
updateUser#20529438 user_id:long = Update;
updateAutoSaveSettings#ec05b097 = Update;
updateStory#75b3b798 peer:Peer story:StoryItem = Update;
updateReadStories#f74e932b peer:Peer max_id:int = Update;
updateStoryID#1bf335b9 id:int random_id:long = Update;
updateStoriesStealthMode#2c084dc1 stealth_mode:StoriesStealthMode = Update;
updateSentStoryReaction#7d627683 peer:Peer story_id:int reaction:Reaction = Update;
updateBotChatBoost#904dd49c peer:Peer boost:Boost qts:int = Update;
updateChannelViewForumAsMessages#7b68920 channel_id:long enabled:Bool = Update;
updatePeerWallpaper#ae3f101d flags:# wallpaper_overridden:flags.1?true peer:Peer wallpaper:flags.0?WallPaper = Update;
updateBotMessageReaction#ac21d3ce peer:Peer msg_id:int date:int actor:Peer old_reactions:Vector<Reaction> new_reactions:Vector<Reaction> qts:int = Update;
updateBotMessageReactions#9cb7759 peer:Peer msg_id:int date:int reactions:Vector<ReactionCount> qts:int = Update;
updateSavedDialogPinned#aeaf9e74 flags:# pinned:flags.0?true peer:DialogPeer = Update;
updatePinnedSavedDialogs#686c85a6 flags:# order:flags.0?Vector<DialogPeer> = Update;
updateSavedReactionTags#39c67432 = Update;
updateSmsJob#f16269d4 job_id:string = Update;
updateQuickReplies#f9470ab2 quick_replies:Vector<QuickReply> = Update;
updateNewQuickReply#f53da717 quick_reply:QuickReply = Update;
updateDeleteQuickReply#53e6f1ec shortcut_id:int = Update;
updateQuickReplyMessage#3e050d0f message:Message = Update;
updateDeleteQuickReplyMessages#566fe7cd shortcut_id:int messages:Vector<int> = Update;
updateBotBusinessConnect#8ae5c97a connection:BotBusinessConnection qts:int = Update;
updateBotNewBusinessMessage#9ddb347c flags:# connection_id:string message:Message reply_to_message:flags.0?Message qts:int = Update;
updateBotEditBusinessMessage#7df587c flags:# connection_id:string message:Message reply_to_message:flags.0?Message qts:int = Update;
updateBotDeleteBusinessMessage#a02a982e connection_id:string peer:Peer messages:Vector<int> qts:int = Update;
updateNewStoryReaction#1824e40b story_id:int peer:Peer reaction:Reaction = Update;
updateStarsBalance#4e80a379 balance:StarsAmount = Update;
updateBusinessBotCallbackQuery#1ea2fda7 flags:# query_id:long user_id:long connection_id:string message:Message reply_to_message:flags.2?Message chat_instance:long data:flags.0?bytes = Update;
updateStarsRevenueStatus#a584b019 peer:Peer status:StarsRevenueStatus = Update;
updateBotPurchasedPaidMedia#283bd312 user_id:long payload:string qts:int = Update;
updatePaidReactionPrivacy#8b725fce private:PaidReactionPrivacy = Update;
updateSentPhoneCode#504aa18f sent_code:auth.SentCode = Update;
updateGroupCallChainBlocks#a477288f call:InputGroupCall sub_chain_id:int blocks:Vector<bytes> next_offset:int = Update;
updateReadMonoForumInbox#77b0e372 channel_id:long saved_peer_id:Peer read_max_id:int = Update;
updateReadMonoForumOutbox#a4a79376 channel_id:long saved_peer_id:Peer read_max_id:int = Update;
updateMonoForumNoPaidException#9f812b08 flags:# exception:flags.0?true channel_id:long saved_peer_id:Peer = Update;

updates.state#a56c2a3e pts:int qts:int date:int seq:int unread_count:int = updates.State;

updates.differenceEmpty#5d75a138 date:int seq:int = updates.Difference;
updates.difference#f49ca0 new_messages:Vector<Message> new_encrypted_messages:Vector<EncryptedMessage> other_updates:Vector<Update> chats:Vector<Chat> users:Vector<User> state:updates.State = updates.Difference;
updates.differenceSlice#a8fb1981 new_messages:Vector<Message> new_encrypted_messages:Vector<EncryptedMessage> other_updates:Vector<Update> chats:Vector<Chat> users:Vector<User> intermediate_state:updates.State = updates.Difference;
updates.differenceTooLong#4afe8f6d pts:int = updates.Difference;

updatesTooLong#e317af7e = Updates;
updateShortMessage#313bc7f8 flags:# out:flags.1?true mentioned:flags.4?true media_unread:flags.5?true silent:flags.13?true id:int user_id:long message:string pts:int pts_count:int date:int fwd_from:flags.2?MessageFwdHeader via_bot_id:flags.11?long reply_to:flags.3?MessageReplyHeader entities:flags.7?Vector<MessageEntity> ttl_period:flags.25?int = Updates;
updateShortChatMessage#4d6deea5 flags:# out:flags.1?true mentioned:flags.4?true media_unread:flags.5?true silent:flags.13?true id:int from_id:long chat_id:long message:string pts:int pts_count:int date:int fwd_from:flags.2?MessageFwdHeader via_bot_id:flags.11?long reply_to:flags.3?MessageReplyHeader entities:flags.7?Vector<MessageEntity> ttl_period:flags.25?int = Updates;
updateShort#78d4dec1 update:Update date:int = Updates;
updatesCombined#725b04c3 updates:Vector<Update> users:Vector<User> chats:Vector<Chat> date:int seq_start:int seq:int = Updates;
updates#74ae4240 updates:Vector<Update> users:Vector<User> chats:Vector<Chat> date:int seq:int = Updates;
updateShortSentMessage#9015e101 flags:# out:flags.1?true id:int pts:int pts_count:int date:int media:flags.9?MessageMedia entities:flags.7?Vector<MessageEntity> ttl_period:flags.25?int = Updates;

photos.photos#8dca6aa5 photos:Vector<Photo> users:Vector<User> = photos.Photos;
photos.photosSlice#15051f54 count:int photos:Vector<Photo> users:Vector<User> = photos.Photos;

photos.photo#20212ca8 photo:Photo users:Vector<User> = photos.Photo;

upload.file#96a18d5 type:storage.FileType mtime:int bytes:bytes = upload.File;
upload.fileCdnRedirect#f18cda44 dc_id:int file_token:bytes encryption_key:bytes encryption_iv:bytes file_hashes:Vector<FileHash> = upload.File;

dcOption#18b7a10d flags:# ipv6:flags.0?true media_only:flags.1?true tcpo_only:flags.2?true cdn:flags.3?true static:flags.4?true this_port_only:flags.5?true id:int ip_address:string port:int secret:flags.10?bytes = DcOption;

config#cc1a241e flags:# default_p2p_contacts:flags.3?true preload_featured_stickers:flags.4?true revoke_pm_inbox:flags.6?true blocked_mode:flags.8?true force_try_ipv6:flags.14?true date:int expires:int test_mode:Bool this_dc:int dc_options:Vector<DcOption> dc_txt_domain_name:string chat_size_max:int megagroup_size_max:int forwarded_count_max:int online_update_period_ms:int offline_blur_timeout_ms:int offline_idle_timeout_ms:int online_cloud_timeout_ms:int notify_cloud_delay_ms:int notify_default_delay_ms:int push_chat_period_ms:int push_chat_limit:int edit_time_limit:int revoke_time_limit:int revoke_pm_time_limit:int rating_e_decay:int stickers_recent_limit:int channels_read_media_period:int tmp_sessions:flags.0?int call_receive_timeout_ms:int call_ring_timeout_ms:int call_connect_timeout_ms:int call_packet_timeout_ms:int me_url_prefix:string autoupdate_url_prefix:flags.7?string gif_search_username:flags.9?string venue_search_username:flags.10?string img_search_username:flags.11?string static_maps_provider:flags.12?string caption_length_max:int message_length_max:int webfile_dc_id:int suggested_lang_code:flags.2?string lang_pack_version:flags.2?int base_lang_pack_version:flags.2?int reactions_default:flags.15?Reaction autologin_token:flags.16?string = Config;

nearestDc#8e1a1775 country:string this_dc:int nearest_dc:int = NearestDc;

help.appUpdate#ccbbce30 flags:# can_not_skip:flags.0?true id:int version:string text:string entities:Vector<MessageEntity> document:flags.1?Document url:flags.2?string sticker:flags.3?Document = help.AppUpdate;
help.noAppUpdate#c45a6536 = help.AppUpdate;

help.inviteText#18cb9f78 message:string = help.InviteText;

encryptedChatEmpty#ab7ec0a0 id:int = EncryptedChat;
encryptedChatWaiting#66b25953 id:int access_hash:long date:int admin_id:long participant_id:long = EncryptedChat;
encryptedChatRequested#48f1d94c flags:# folder_id:flags.0?int id:int access_hash:long date:int admin_id:long participant_id:long g_a:bytes = EncryptedChat;
encryptedChat#61f0d4c7 id:int access_hash:long date:int admin_id:long participant_id:long g_a_or_b:bytes key_fingerprint:long = EncryptedChat;
encryptedChatDiscarded#1e1c7c45 flags:# history_deleted:flags.0?true id:int = EncryptedChat;

inputEncryptedChat#f141b5e1 chat_id:int access_hash:long = InputEncryptedChat;

encryptedFileEmpty#c21f497e = EncryptedFile;
encryptedFile#a8008cd8 id:long access_hash:long size:long dc_id:int key_fingerprint:int = EncryptedFile;

inputEncryptedFileEmpty#1837c364 = InputEncryptedFile;
inputEncryptedFileUploaded#64bd0306 id:long parts:int md5_checksum:string key_fingerprint:int = InputEncryptedFile;
inputEncryptedFile#5a17b5e5 id:long access_hash:long = InputEncryptedFile;
inputEncryptedFileBigUploaded#2dc173c8 id:long parts:int key_fingerprint:int = InputEncryptedFile;

encryptedMessage#ed18c118 random_id:long chat_id:int date:int bytes:bytes file:EncryptedFile = EncryptedMessage;
encryptedMessageService#23734b06 random_id:long chat_id:int date:int bytes:bytes = EncryptedMessage;

messages.dhConfigNotModified#c0e24635 random:bytes = messages.DhConfig;
messages.dhConfig#2c221edd g:int p:bytes version:int random:bytes = messages.DhConfig;

messages.sentEncryptedMessage#560f8935 date:int = messages.SentEncryptedMessage;
messages.sentEncryptedFile#9493ff32 date:int file:EncryptedFile = messages.SentEncryptedMessage;

inputDocumentEmpty#72f0eaae = InputDocument;
inputDocument#1abfb575 id:long access_hash:long file_reference:bytes = InputDocument;

documentEmpty#36f8c871 id:long = Document;
document#8fd4c4d8 flags:# id:long access_hash:long file_reference:bytes date:int mime_type:string size:long thumbs:flags.0?Vector<PhotoSize> video_thumbs:flags.1?Vector<VideoSize> dc_id:int attributes:Vector<DocumentAttribute> = Document;

help.support#17c6b5f6 phone_number:string user:User = help.Support;

notifyPeer#9fd40bd8 peer:Peer = NotifyPeer;
notifyUsers#b4c83b4c = NotifyPeer;
notifyChats#c007cec3 = NotifyPeer;
notifyBroadcasts#d612e8ef = NotifyPeer;
notifyForumTopic#226e6308 peer:Peer top_msg_id:int = NotifyPeer;

sendMessageTypingAction#16bf744e = SendMessageAction;
sendMessageCancelAction#fd5ec8f5 = SendMessageAction;
sendMessageRecordVideoAction#a187d66f = SendMessageAction;
sendMessageUploadVideoAction#e9763aec progress:int = SendMessageAction;
sendMessageRecordAudioAction#d52f73f7 = SendMessageAction;
sendMessageUploadAudioAction#f351d7ab progress:int = SendMessageAction;
sendMessageUploadPhotoAction#d1d34a26 progress:int = SendMessageAction;
sendMessageUploadDocumentAction#aa0cd9e4 progress:int = SendMessageAction;
sendMessageGeoLocationAction#176f8ba1 = SendMessageAction;
sendMessageChooseContactAction#628cbc6f = SendMessageAction;
sendMessageGamePlayAction#dd6a8f48 = SendMessageAction;
sendMessageRecordRoundAction#88f27fbc = SendMessageAction;
sendMessageUploadRoundAction#243e1c66 progress:int = SendMessageAction;
speakingInGroupCallAction#d92c2285 = SendMessageAction;
sendMessageHistoryImportAction#dbda9246 progress:int = SendMessageAction;
sendMessageChooseStickerAction#b05ac6b1 = SendMessageAction;
sendMessageEmojiInteraction#25972bcb emoticon:string msg_id:int interaction:DataJSON = SendMessageAction;
sendMessageEmojiInteractionSeen#b665902e emoticon:string = SendMessageAction;

contacts.found#b3134d9d my_results:Vector<Peer> results:Vector<Peer> chats:Vector<Chat> users:Vector<User> = contacts.Found;

inputPrivacyKeyStatusTimestamp#4f96cb18 = InputPrivacyKey;
inputPrivacyKeyChatInvite#bdfb0426 = InputPrivacyKey;
inputPrivacyKeyPhoneCall#fabadc5f = InputPrivacyKey;
inputPrivacyKeyPhoneP2P#db9e70d2 = InputPrivacyKey;
inputPrivacyKeyForwards#a4dd4c08 = InputPrivacyKey;
inputPrivacyKeyProfilePhoto#5719bacc = InputPrivacyKey;
inputPrivacyKeyPhoneNumber#352dafa = InputPrivacyKey;
inputPrivacyKeyAddedByPhone#d1219bdd = InputPrivacyKey;
inputPrivacyKeyVoiceMessages#aee69d68 = InputPrivacyKey;
inputPrivacyKeyAbout#3823cc40 = InputPrivacyKey;
inputPrivacyKeyBirthday#d65a11cc = InputPrivacyKey;
inputPrivacyKeyStarGiftsAutoSave#e1732341 = InputPrivacyKey;
inputPrivacyKeyNoPaidMessages#bdc597b4 = InputPrivacyKey;

privacyKeyStatusTimestamp#bc2eab30 = PrivacyKey;
privacyKeyChatInvite#500e6dfa = PrivacyKey;
privacyKeyPhoneCall#3d662b7b = PrivacyKey;
privacyKeyPhoneP2P#39491cc8 = PrivacyKey;
privacyKeyForwards#69ec56a3 = PrivacyKey;
privacyKeyProfilePhoto#96151fed = PrivacyKey;
privacyKeyPhoneNumber#d19ae46d = PrivacyKey;
privacyKeyAddedByPhone#42ffd42b = PrivacyKey;
privacyKeyVoiceMessages#697f414 = PrivacyKey;
privacyKeyAbout#a486b761 = PrivacyKey;
privacyKeyBirthday#2000a518 = PrivacyKey;
privacyKeyStarGiftsAutoSave#2ca4fdf8 = PrivacyKey;
privacyKeyNoPaidMessages#17d348d2 = PrivacyKey;

inputPrivacyValueAllowContacts#d09e07b = InputPrivacyRule;
inputPrivacyValueAllowAll#184b35ce = InputPrivacyRule;
inputPrivacyValueAllowUsers#131cc67f users:Vector<InputUser> = InputPrivacyRule;
inputPrivacyValueDisallowContacts#ba52007 = InputPrivacyRule;
inputPrivacyValueDisallowAll#d66b66c9 = InputPrivacyRule;
inputPrivacyValueDisallowUsers#90110467 users:Vector<InputUser> = InputPrivacyRule;
inputPrivacyValueAllowChatParticipants#840649cf chats:Vector<long> = InputPrivacyRule;
inputPrivacyValueDisallowChatParticipants#e94f0f86 chats:Vector<long> = InputPrivacyRule;
inputPrivacyValueAllowCloseFriends#2f453e49 = InputPrivacyRule;
inputPrivacyValueAllowPremium#77cdc9f1 = InputPrivacyRule;
inputPrivacyValueAllowBots#5a4fcce5 = InputPrivacyRule;
inputPrivacyValueDisallowBots#c4e57915 = InputPrivacyRule;

privacyValueAllowContacts#fffe1bac = PrivacyRule;
privacyValueAllowAll#65427b82 = PrivacyRule;
privacyValueAllowUsers#b8905fb2 users:Vector<long> = PrivacyRule;
privacyValueDisallowContacts#f888fa1a = PrivacyRule;
privacyValueDisallowAll#8b73e763 = PrivacyRule;
privacyValueDisallowUsers#e4621141 users:Vector<long> = PrivacyRule;
privacyValueAllowChatParticipants#6b134e8e chats:Vector<long> = PrivacyRule;
privacyValueDisallowChatParticipants#41c87565 chats:Vector<long> = PrivacyRule;
privacyValueAllowCloseFriends#f7e8d89b = PrivacyRule;
privacyValueAllowPremium#ece9814b = PrivacyRule;
privacyValueAllowBots#21461b5d = PrivacyRule;
privacyValueDisallowBots#f6a5f82f = PrivacyRule;

account.privacyRules#50a04e45 rules:Vector<PrivacyRule> chats:Vector<Chat> users:Vector<User> = account.PrivacyRules;

accountDaysTTL#b8d0afdf days:int = AccountDaysTTL;

documentAttributeImageSize#6c37c15c w:int h:int = DocumentAttribute;
documentAttributeAnimated#11b58939 = DocumentAttribute;
documentAttributeSticker#6319d612 flags:# mask:flags.1?true alt:string stickerset:InputStickerSet mask_coords:flags.0?MaskCoords = DocumentAttribute;
documentAttributeVideo#43c57c48 flags:# round_message:flags.0?true supports_streaming:flags.1?true nosound:flags.3?true duration:double w:int h:int preload_prefix_size:flags.2?int video_start_ts:flags.4?double video_codec:flags.5?string = DocumentAttribute;
documentAttributeAudio#9852f9c6 flags:# voice:flags.10?true duration:int title:flags.0?string performer:flags.1?string waveform:flags.2?bytes = DocumentAttribute;
documentAttributeFilename#15590068 file_name:string = DocumentAttribute;
documentAttributeHasStickers#9801d2f7 = DocumentAttribute;
documentAttributeCustomEmoji#fd149899 flags:# free:flags.0?true text_color:flags.1?true alt:string stickerset:InputStickerSet = DocumentAttribute;

messages.stickersNotModified#f1749a22 = messages.Stickers;
messages.stickers#30a6ec7e hash:long stickers:Vector<Document> = messages.Stickers;

stickerPack#12b299d4 emoticon:string documents:Vector<long> = StickerPack;

messages.allStickersNotModified#e86602c3 = messages.AllStickers;
messages.allStickers#cdbbcebb hash:long sets:Vector<StickerSet> = messages.AllStickers;

messages.affectedMessages#84d19185 pts:int pts_count:int = messages.AffectedMessages;

webPageEmpty#211a1788 flags:# id:long url:flags.0?string = WebPage;
webPagePending#b0d13e47 flags:# id:long url:flags.0?string date:int = WebPage;
webPage#e89c45b2 flags:# has_large_media:flags.13?true video_cover_photo:flags.14?true id:long url:string display_url:string hash:int type:flags.0?string site_name:flags.1?string title:flags.2?string description:flags.3?string photo:flags.4?Photo embed_url:flags.5?string embed_type:flags.5?string embed_width:flags.6?int embed_height:flags.6?int duration:flags.7?int author:flags.8?string document:flags.9?Document cached_page:flags.10?Page attributes:flags.12?Vector<WebPageAttribute> = WebPage;
webPageNotModified#7311ca11 flags:# cached_page_views:flags.0?int = WebPage;

authorization#ad01d61d flags:# current:flags.0?true official_app:flags.1?true password_pending:flags.2?true encrypted_requests_disabled:flags.3?true call_requests_disabled:flags.4?true unconfirmed:flags.5?true hash:long device_model:string platform:string system_version:string api_id:int app_name:string app_version:string date_created:int date_active:int ip:string country:string region:string = Authorization;

account.authorizations#4bff8ea0 authorization_ttl_days:int authorizations:Vector<Authorization> = account.Authorizations;

account.password#957b50fb flags:# has_recovery:flags.0?true has_secure_values:flags.1?true has_password:flags.2?true current_algo:flags.2?PasswordKdfAlgo srp_B:flags.2?bytes srp_id:flags.2?long hint:flags.3?string email_unconfirmed_pattern:flags.4?string new_algo:PasswordKdfAlgo new_secure_algo:SecurePasswordKdfAlgo secure_random:bytes pending_reset_date:flags.5?int login_email_pattern:flags.6?string = account.Password;

account.passwordSettings#9a5c33e5 flags:# email:flags.0?string secure_settings:flags.1?SecureSecretSettings = account.PasswordSettings;

account.passwordInputSettings#c23727c9 flags:# new_algo:flags.0?PasswordKdfAlgo new_password_hash:flags.0?bytes hint:flags.0?string email:flags.1?string new_secure_settings:flags.2?SecureSecretSettings = account.PasswordInputSettings;

auth.passwordRecovery#137948a5 email_pattern:string = auth.PasswordRecovery;

receivedNotifyMessage#a384b779 id:int flags:int = ReceivedNotifyMessage;

chatInviteExported#a22cbd96 flags:# revoked:flags.0?true permanent:flags.5?true request_needed:flags.6?true link:string admin_id:long date:int start_date:flags.4?int expire_date:flags.1?int usage_limit:flags.2?int usage:flags.3?int requested:flags.7?int subscription_expired:flags.10?int title:flags.8?string subscription_pricing:flags.9?StarsSubscriptionPricing = ExportedChatInvite;
chatInvitePublicJoinRequests#ed107ab7 = ExportedChatInvite;

chatInviteAlready#5a686d7c chat:Chat = ChatInvite;
chatInvite#5c9d3702 flags:# channel:flags.0?true broadcast:flags.1?true public:flags.2?true megagroup:flags.3?true request_needed:flags.6?true verified:flags.7?true scam:flags.8?true fake:flags.9?true can_refulfill_subscription:flags.11?true title:string about:flags.5?string photo:Photo participants_count:int participants:flags.4?Vector<User> color:int subscription_pricing:flags.10?StarsSubscriptionPricing subscription_form_id:flags.12?long bot_verification:flags.13?BotVerification = ChatInvite;
chatInvitePeek#61695cb0 chat:Chat expires:int = ChatInvite;

inputStickerSetEmpty#ffb62b95 = InputStickerSet;
inputStickerSetID#9de7a269 id:long access_hash:long = InputStickerSet;
inputStickerSetShortName#861cc8a0 short_name:string = InputStickerSet;
inputStickerSetAnimatedEmoji#28703c8 = InputStickerSet;
inputStickerSetDice#e67f520e emoticon:string = InputStickerSet;
inputStickerSetAnimatedEmojiAnimations#cde3739 = InputStickerSet;
inputStickerSetPremiumGifts#c88b3b02 = InputStickerSet;
inputStickerSetEmojiGenericAnimations#4c4d4ce = InputStickerSet;
inputStickerSetEmojiDefaultStatuses#29d0f5ee = InputStickerSet;
inputStickerSetEmojiDefaultTopicIcons#44c1f8e9 = InputStickerSet;
inputStickerSetEmojiChannelDefaultStatuses#49748553 = InputStickerSet;
inputStickerSetTonGifts#1cf671a0 = InputStickerSet;

stickerSet#2dd14edc flags:# archived:flags.1?true official:flags.2?true masks:flags.3?true emojis:flags.7?true text_color:flags.9?true channel_emoji_status:flags.10?true creator:flags.11?true installed_date:flags.0?int id:long access_hash:long title:string short_name:string thumbs:flags.4?Vector<PhotoSize> thumb_dc_id:flags.4?int thumb_version:flags.4?int thumb_document_id:flags.8?long count:int hash:int = StickerSet;

messages.stickerSet#6e153f16 set:StickerSet packs:Vector<StickerPack> keywords:Vector<StickerKeyword> documents:Vector<Document> = messages.StickerSet;
messages.stickerSetNotModified#d3f924eb = messages.StickerSet;

botCommand#c27ac8c7 command:string description:string = BotCommand;

botInfo#4d8a0299 flags:# has_preview_medias:flags.6?true user_id:flags.0?long description:flags.1?string description_photo:flags.4?Photo description_document:flags.5?Document commands:flags.2?Vector<BotCommand> menu_button:flags.3?BotMenuButton privacy_policy_url:flags.7?string app_settings:flags.8?BotAppSettings verifier_settings:flags.9?BotVerifierSettings = BotInfo;

keyboardButton#a2fa4880 text:string = KeyboardButton;
keyboardButtonUrl#258aff05 text:string url:string = KeyboardButton;
keyboardButtonCallback#35bbdb6b flags:# requires_password:flags.0?true text:string data:bytes = KeyboardButton;
keyboardButtonRequestPhone#b16a6c29 text:string = KeyboardButton;
keyboardButtonRequestGeoLocation#fc796b3f text:string = KeyboardButton;
keyboardButtonSwitchInline#93b9fbb5 flags:# same_peer:flags.0?true text:string query:string peer_types:flags.1?Vector<InlineQueryPeerType> = KeyboardButton;
keyboardButtonGame#50f41ccf text:string = KeyboardButton;
keyboardButtonBuy#afd93fbb text:string = KeyboardButton;
keyboardButtonUrlAuth#10b78d29 flags:# text:string fwd_text:flags.0?string url:string button_id:int = KeyboardButton;
inputKeyboardButtonUrlAuth#d02e7fd4 flags:# request_write_access:flags.0?true text:string fwd_text:flags.1?string url:string bot:InputUser = KeyboardButton;
keyboardButtonRequestPoll#bbc7515d flags:# quiz:flags.0?Bool text:string = KeyboardButton;
inputKeyboardButtonUserProfile#e988037b text:string user_id:InputUser = KeyboardButton;
keyboardButtonUserProfile#308660c1 text:string user_id:long = KeyboardButton;
keyboardButtonWebView#13767230 text:string url:string = KeyboardButton;
keyboardButtonSimpleWebView#a0c0505c text:string url:string = KeyboardButton;
keyboardButtonRequestPeer#53d7bfd8 text:string button_id:int peer_type:RequestPeerType max_quantity:int = KeyboardButton;
inputKeyboardButtonRequestPeer#c9662d05 flags:# name_requested:flags.0?true username_requested:flags.1?true photo_requested:flags.2?true text:string button_id:int peer_type:RequestPeerType max_quantity:int = KeyboardButton;
keyboardButtonCopy#75d2698e text:string copy_text:string = KeyboardButton;

keyboardButtonRow#77608b83 buttons:Vector<KeyboardButton> = KeyboardButtonRow;

replyKeyboardHide#a03e5b85 flags:# selective:flags.2?true = ReplyMarkup;
replyKeyboardForceReply#86b40b08 flags:# single_use:flags.1?true selective:flags.2?true placeholder:flags.3?string = ReplyMarkup;
replyKeyboardMarkup#85dd99d1 flags:# resize:flags.0?true single_use:flags.1?true selective:flags.2?true persistent:flags.4?true rows:Vector<KeyboardButtonRow> placeholder:flags.3?string = ReplyMarkup;
replyInlineMarkup#48a30254 rows:Vector<KeyboardButtonRow> = ReplyMarkup;

messageEntityUnknown#bb92ba95 offset:int length:int = MessageEntity;
messageEntityMention#fa04579d offset:int length:int = MessageEntity;
messageEntityHashtag#6f635b0d offset:int length:int = MessageEntity;
messageEntityBotCommand#6cef8ac7 offset:int length:int = MessageEntity;
messageEntityUrl#6ed02538 offset:int length:int = MessageEntity;
messageEntityEmail#64e475c2 offset:int length:int = MessageEntity;
messageEntityBold#bd610bc9 offset:int length:int = MessageEntity;
messageEntityItalic#826f8b60 offset:int length:int = MessageEntity;
messageEntityCode#28a20571 offset:int length:int = MessageEntity;
messageEntityPre#73924be0 offset:int length:int language:string = MessageEntity;
messageEntityTextUrl#76a6d327 offset:int length:int url:string = MessageEntity;
messageEntityMentionName#dc7b1140 offset:int length:int user_id:long = MessageEntity;
inputMessageEntityMentionName#208e68c9 offset:int length:int user_id:InputUser = MessageEntity;
messageEntityPhone#9b69e34b offset:int length:int = MessageEntity;
messageEntityCashtag#4c4e743f offset:int length:int = MessageEntity;
messageEntityUnderline#9c4e7e8b offset:int length:int = MessageEntity;
messageEntityStrike#bf0693d4 offset:int length:int = MessageEntity;
messageEntityBankCard#761e6af4 offset:int length:int = MessageEntity;
messageEntitySpoiler#32ca960f offset:int length:int = MessageEntity;
messageEntityCustomEmoji#c8cf05f8 offset:int length:int document_id:long = MessageEntity;
messageEntityBlockquote#f1ccaaac flags:# collapsed:flags.0?true offset:int length:int = MessageEntity;

inputChannelEmpty#ee8c1e86 = InputChannel;
inputChannel#f35aec28 channel_id:long access_hash:long = InputChannel;
inputChannelFromMessage#5b934f9d peer:InputPeer msg_id:int channel_id:long = InputChannel;

contacts.resolvedPeer#7f077ad9 peer:Peer chats:Vector<Chat> users:Vector<User> = contacts.ResolvedPeer;

messageRange#ae30253 min_id:int max_id:int = MessageRange;

updates.channelDifferenceEmpty#3e11affb flags:# final:flags.0?true pts:int timeout:flags.1?int = updates.ChannelDifference;
updates.channelDifferenceTooLong#a4bcc6fe flags:# final:flags.0?true timeout:flags.1?int dialog:Dialog messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = updates.ChannelDifference;
updates.channelDifference#2064674e flags:# final:flags.0?true pts:int timeout:flags.1?int new_messages:Vector<Message> other_updates:Vector<Update> chats:Vector<Chat> users:Vector<User> = updates.ChannelDifference;

channelMessagesFilterEmpty#94d42ee7 = ChannelMessagesFilter;
channelMessagesFilter#cd77d957 flags:# exclude_new_messages:flags.1?true ranges:Vector<MessageRange> = ChannelMessagesFilter;

channelParticipant#cb397619 flags:# user_id:long date:int subscription_until_date:flags.0?int = ChannelParticipant;
channelParticipantSelf#4f607bef flags:# via_request:flags.0?true user_id:long inviter_id:long date:int subscription_until_date:flags.1?int = ChannelParticipant;
channelParticipantCreator#2fe601d3 flags:# user_id:long admin_rights:ChatAdminRights rank:flags.0?string = ChannelParticipant;
channelParticipantAdmin#34c3bb53 flags:# can_edit:flags.0?true self:flags.1?true user_id:long inviter_id:flags.1?long promoted_by:long date:int admin_rights:ChatAdminRights rank:flags.2?string = ChannelParticipant;
channelParticipantBanned#6df8014e flags:# left:flags.0?true peer:Peer kicked_by:long date:int banned_rights:ChatBannedRights = ChannelParticipant;
channelParticipantLeft#1b03f006 peer:Peer = ChannelParticipant;

channelParticipantsRecent#de3f3c79 = ChannelParticipantsFilter;
channelParticipantsAdmins#b4608969 = ChannelParticipantsFilter;
channelParticipantsKicked#a3b54985 q:string = ChannelParticipantsFilter;
channelParticipantsBots#b0d1865b = ChannelParticipantsFilter;
channelParticipantsBanned#1427a5e1 q:string = ChannelParticipantsFilter;
channelParticipantsSearch#656ac4b q:string = ChannelParticipantsFilter;
channelParticipantsContacts#bb6ae88d q:string = ChannelParticipantsFilter;
channelParticipantsMentions#e04b5ceb flags:# q:flags.0?string top_msg_id:flags.1?int = ChannelParticipantsFilter;

channels.channelParticipants#9ab0feaf count:int participants:Vector<ChannelParticipant> chats:Vector<Chat> users:Vector<User> = channels.ChannelParticipants;
channels.channelParticipantsNotModified#f0173fe9 = channels.ChannelParticipants;

channels.channelParticipant#dfb80317 participant:ChannelParticipant chats:Vector<Chat> users:Vector<User> = channels.ChannelParticipant;

help.termsOfService#780a0310 flags:# popup:flags.0?true id:DataJSON text:string entities:Vector<MessageEntity> min_age_confirm:flags.1?int = help.TermsOfService;

messages.savedGifsNotModified#e8025ca2 = messages.SavedGifs;
messages.savedGifs#84a02a0d hash:long gifs:Vector<Document> = messages.SavedGifs;

inputBotInlineMessageMediaAuto#3380c786 flags:# invert_media:flags.3?true message:string entities:flags.1?Vector<MessageEntity> reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;
inputBotInlineMessageText#3dcd7a87 flags:# no_webpage:flags.0?true invert_media:flags.3?true message:string entities:flags.1?Vector<MessageEntity> reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;
inputBotInlineMessageMediaGeo#96929a85 flags:# geo_point:InputGeoPoint heading:flags.0?int period:flags.1?int proximity_notification_radius:flags.3?int reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;
inputBotInlineMessageMediaVenue#417bbf11 flags:# geo_point:InputGeoPoint title:string address:string provider:string venue_id:string venue_type:string reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;
inputBotInlineMessageMediaContact#a6edbffd flags:# phone_number:string first_name:string last_name:string vcard:string reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;
inputBotInlineMessageGame#4b425864 flags:# reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;
inputBotInlineMessageMediaInvoice#d7e78225 flags:# title:string description:string photo:flags.0?InputWebDocument invoice:Invoice payload:bytes provider:string provider_data:DataJSON reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;
inputBotInlineMessageMediaWebPage#bddcc510 flags:# invert_media:flags.3?true force_large_media:flags.4?true force_small_media:flags.5?true optional:flags.6?true message:string entities:flags.1?Vector<MessageEntity> url:string reply_markup:flags.2?ReplyMarkup = InputBotInlineMessage;

inputBotInlineResult#88bf9319 flags:# id:string type:string title:flags.1?string description:flags.2?string url:flags.3?string thumb:flags.4?InputWebDocument content:flags.5?InputWebDocument send_message:InputBotInlineMessage = InputBotInlineResult;
inputBotInlineResultPhoto#a8d864a7 id:string type:string photo:InputPhoto send_message:InputBotInlineMessage = InputBotInlineResult;
inputBotInlineResultDocument#fff8fdc4 flags:# id:string type:string title:flags.1?string description:flags.2?string document:InputDocument send_message:InputBotInlineMessage = InputBotInlineResult;
inputBotInlineResultGame#4fa417f2 id:string short_name:string send_message:InputBotInlineMessage = InputBotInlineResult;

botInlineMessageMediaAuto#764cf810 flags:# invert_media:flags.3?true message:string entities:flags.1?Vector<MessageEntity> reply_markup:flags.2?ReplyMarkup = BotInlineMessage;
botInlineMessageText#8c7f65e2 flags:# no_webpage:flags.0?true invert_media:flags.3?true message:string entities:flags.1?Vector<MessageEntity> reply_markup:flags.2?ReplyMarkup = BotInlineMessage;
botInlineMessageMediaGeo#51846fd flags:# geo:GeoPoint heading:flags.0?int period:flags.1?int proximity_notification_radius:flags.3?int reply_markup:flags.2?ReplyMarkup = BotInlineMessage;
botInlineMessageMediaVenue#8a86659c flags:# geo:GeoPoint title:string address:string provider:string venue_id:string venue_type:string reply_markup:flags.2?ReplyMarkup = BotInlineMessage;
botInlineMessageMediaContact#18d1cdc2 flags:# phone_number:string first_name:string last_name:string vcard:string reply_markup:flags.2?ReplyMarkup = BotInlineMessage;
botInlineMessageMediaInvoice#354a9b09 flags:# shipping_address_requested:flags.1?true test:flags.3?true title:string description:string photo:flags.0?WebDocument currency:string total_amount:long reply_markup:flags.2?ReplyMarkup = BotInlineMessage;
botInlineMessageMediaWebPage#809ad9a6 flags:# invert_media:flags.3?true force_large_media:flags.4?true force_small_media:flags.5?true manual:flags.7?true safe:flags.8?true message:string entities:flags.1?Vector<MessageEntity> url:string reply_markup:flags.2?ReplyMarkup = BotInlineMessage;

botInlineResult#11965f3a flags:# id:string type:string title:flags.1?string description:flags.2?string url:flags.3?string thumb:flags.4?WebDocument content:flags.5?WebDocument send_message:BotInlineMessage = BotInlineResult;
botInlineMediaResult#17db940b flags:# id:string type:string photo:flags.0?Photo document:flags.1?Document title:flags.2?string description:flags.3?string send_message:BotInlineMessage = BotInlineResult;

messages.botResults#e021f2f6 flags:# gallery:flags.0?true query_id:long next_offset:flags.1?string switch_pm:flags.2?InlineBotSwitchPM switch_webview:flags.3?InlineBotWebView results:Vector<BotInlineResult> cache_time:int users:Vector<User> = messages.BotResults;

exportedMessageLink#5dab1af4 link:string html:string = ExportedMessageLink;

messageFwdHeader#4e4df4bb flags:# imported:flags.7?true saved_out:flags.11?true from_id:flags.0?Peer from_name:flags.5?string date:int channel_post:flags.2?int post_author:flags.3?string saved_from_peer:flags.4?Peer saved_from_msg_id:flags.4?int saved_from_id:flags.8?Peer saved_from_name:flags.9?string saved_date:flags.10?int psa_type:flags.6?string = MessageFwdHeader;

auth.codeTypeSms#72a3158c = auth.CodeType;
auth.codeTypeCall#741cd3e3 = auth.CodeType;
auth.codeTypeFlashCall#226ccefb = auth.CodeType;
auth.codeTypeMissedCall#d61ad6ee = auth.CodeType;
auth.codeTypeFragmentSms#6ed998c = auth.CodeType;

auth.sentCodeTypeApp#3dbb5986 length:int = auth.SentCodeType;
auth.sentCodeTypeSms#c000bba2 length:int = auth.SentCodeType;
auth.sentCodeTypeCall#5353e5a7 length:int = auth.SentCodeType;
auth.sentCodeTypeFlashCall#ab03c6d9 pattern:string = auth.SentCodeType;
auth.sentCodeTypeMissedCall#82006484 prefix:string length:int = auth.SentCodeType;
auth.sentCodeTypeEmailCode#f450f59b flags:# apple_signin_allowed:flags.0?true google_signin_allowed:flags.1?true email_pattern:string length:int reset_available_period:flags.3?int reset_pending_date:flags.4?int = auth.SentCodeType;
auth.sentCodeTypeSetUpEmailRequired#a5491dea flags:# apple_signin_allowed:flags.0?true google_signin_allowed:flags.1?true = auth.SentCodeType;
auth.sentCodeTypeFragmentSms#d9565c39 url:string length:int = auth.SentCodeType;
auth.sentCodeTypeFirebaseSms#9fd736 flags:# nonce:flags.0?bytes play_integrity_project_id:flags.2?long play_integrity_nonce:flags.2?bytes receipt:flags.1?string push_timeout:flags.1?int length:int = auth.SentCodeType;
auth.sentCodeTypeSmsWord#a416ac81 flags:# beginning:flags.0?string = auth.SentCodeType;
auth.sentCodeTypeSmsPhrase#b37794af flags:# beginning:flags.0?string = auth.SentCodeType;

messages.botCallbackAnswer#36585ea4 flags:# alert:flags.1?true has_url:flags.3?true native_ui:flags.4?true message:flags.0?string url:flags.2?string cache_time:int = messages.BotCallbackAnswer;

messages.messageEditData#26b5dde6 flags:# caption:flags.0?true = messages.MessageEditData;

inputBotInlineMessageID#890c3d89 dc_id:int id:long access_hash:long = InputBotInlineMessageID;
inputBotInlineMessageID64#b6d915d7 dc_id:int owner_id:long id:int access_hash:long = InputBotInlineMessageID;

inlineBotSwitchPM#3c20629f text:string start_param:string = InlineBotSwitchPM;

messages.peerDialogs#3371c354 dialogs:Vector<Dialog> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> state:updates.State = messages.PeerDialogs;

topPeer#edcdc05b peer:Peer rating:double = TopPeer;

topPeerCategoryBotsPM#ab661b5b = TopPeerCategory;
topPeerCategoryBotsInline#148677e2 = TopPeerCategory;
topPeerCategoryCorrespondents#637b7ed = TopPeerCategory;
topPeerCategoryGroups#bd17a14a = TopPeerCategory;
topPeerCategoryChannels#161d9628 = TopPeerCategory;
topPeerCategoryPhoneCalls#1e76a78c = TopPeerCategory;
topPeerCategoryForwardUsers#a8406ca9 = TopPeerCategory;
topPeerCategoryForwardChats#fbeec0f0 = TopPeerCategory;
topPeerCategoryBotsApp#fd9e7bec = TopPeerCategory;

topPeerCategoryPeers#fb834291 category:TopPeerCategory count:int peers:Vector<TopPeer> = TopPeerCategoryPeers;

contacts.topPeersNotModified#de266ef5 = contacts.TopPeers;
contacts.topPeers#70b772a8 categories:Vector<TopPeerCategoryPeers> chats:Vector<Chat> users:Vector<User> = contacts.TopPeers;
contacts.topPeersDisabled#b52c939d = contacts.TopPeers;

draftMessageEmpty#1b0c841a flags:# date:flags.0?int = DraftMessage;
draftMessage#96eaa5eb flags:# no_webpage:flags.1?true invert_media:flags.6?true reply_to:flags.4?InputReplyTo message:string entities:flags.3?Vector<MessageEntity> media:flags.5?InputMedia date:int effect:flags.7?long suggested_post:flags.8?SuggestedPost = DraftMessage;

messages.featuredStickersNotModified#c6dc0c66 count:int = messages.FeaturedStickers;
messages.featuredStickers#be382906 flags:# premium:flags.0?true hash:long count:int sets:Vector<StickerSetCovered> unread:Vector<long> = messages.FeaturedStickers;

messages.recentStickersNotModified#b17f890 = messages.RecentStickers;
messages.recentStickers#88d37c56 hash:long packs:Vector<StickerPack> stickers:Vector<Document> dates:Vector<int> = messages.RecentStickers;

messages.archivedStickers#4fcba9c8 count:int sets:Vector<StickerSetCovered> = messages.ArchivedStickers;

messages.stickerSetInstallResultSuccess#38641628 = messages.StickerSetInstallResult;
messages.stickerSetInstallResultArchive#35e410a8 sets:Vector<StickerSetCovered> = messages.StickerSetInstallResult;

stickerSetCovered#6410a5d2 set:StickerSet cover:Document = StickerSetCovered;
stickerSetMultiCovered#3407e51b set:StickerSet covers:Vector<Document> = StickerSetCovered;
stickerSetFullCovered#40d13c0e set:StickerSet packs:Vector<StickerPack> keywords:Vector<StickerKeyword> documents:Vector<Document> = StickerSetCovered;
stickerSetNoCovered#77b15d1c set:StickerSet = StickerSetCovered;

maskCoords#aed6dbb2 n:int x:double y:double zoom:double = MaskCoords;

inputStickeredMediaPhoto#4a992157 id:InputPhoto = InputStickeredMedia;
inputStickeredMediaDocument#438865b id:InputDocument = InputStickeredMedia;

game#bdf9653b flags:# id:long access_hash:long short_name:string title:string description:string photo:Photo document:flags.0?Document = Game;

inputGameID#32c3e77 id:long access_hash:long = InputGame;
inputGameShortName#c331e80a bot_id:InputUser short_name:string = InputGame;

highScore#73a379eb pos:int user_id:long score:int = HighScore;

messages.highScores#9a3bfd99 scores:Vector<HighScore> users:Vector<User> = messages.HighScores;

textEmpty#dc3d824f = RichText;
textPlain#744694e0 text:string = RichText;
textBold#6724abc4 text:RichText = RichText;
textItalic#d912a59c text:RichText = RichText;
textUnderline#c12622c4 text:RichText = RichText;
textStrike#9bf8bb95 text:RichText = RichText;
textFixed#6c3f19b9 text:RichText = RichText;
textUrl#3c2884c1 text:RichText url:string webpage_id:long = RichText;
textEmail#de5a0dd6 text:RichText email:string = RichText;
textConcat#7e6260d7 texts:Vector<RichText> = RichText;
textSubscript#ed6a8504 text:RichText = RichText;
textSuperscript#c7fb5e01 text:RichText = RichText;
textMarked#34b8621 text:RichText = RichText;
textPhone#1ccb966a text:RichText phone:string = RichText;
textImage#81ccf4f document_id:long w:int h:int = RichText;
textAnchor#35553762 text:RichText name:string = RichText;

pageBlockUnsupported#13567e8a = PageBlock;
pageBlockTitle#70abc3fd text:RichText = PageBlock;
pageBlockSubtitle#8ffa9a1f text:RichText = PageBlock;
pageBlockAuthorDate#baafe5e0 author:RichText published_date:int = PageBlock;
pageBlockHeader#bfd064ec text:RichText = PageBlock;
pageBlockSubheader#f12bb6e1 text:RichText = PageBlock;
pageBlockParagraph#467a0766 text:RichText = PageBlock;
pageBlockPreformatted#c070d93e text:RichText language:string = PageBlock;
pageBlockFooter#48870999 text:RichText = PageBlock;
pageBlockDivider#db20b188 = PageBlock;
pageBlockAnchor#ce0d37b0 name:string = PageBlock;
pageBlockList#e4e88011 items:Vector<PageListItem> = PageBlock;
pageBlockBlockquote#263d7c26 text:RichText caption:RichText = PageBlock;
pageBlockPullquote#4f4456d3 text:RichText caption:RichText = PageBlock;
pageBlockPhoto#1759c560 flags:# photo_id:long caption:PageCaption url:flags.0?string webpage_id:flags.0?long = PageBlock;
pageBlockVideo#7c8fe7b6 flags:# autoplay:flags.0?true loop:flags.1?true video_id:long caption:PageCaption = PageBlock;
pageBlockCover#39f23300 cover:PageBlock = PageBlock;
pageBlockEmbed#a8718dc5 flags:# full_width:flags.0?true allow_scrolling:flags.3?true url:flags.1?string html:flags.2?string poster_photo_id:flags.4?long w:flags.5?int h:flags.5?int caption:PageCaption = PageBlock;
pageBlockEmbedPost#f259a80b url:string webpage_id:long author_photo_id:long author:string date:int blocks:Vector<PageBlock> caption:PageCaption = PageBlock;
pageBlockCollage#65a0fa4d items:Vector<PageBlock> caption:PageCaption = PageBlock;
pageBlockSlideshow#31f9590 items:Vector<PageBlock> caption:PageCaption = PageBlock;
pageBlockChannel#ef1751b5 channel:Chat = PageBlock;
pageBlockAudio#804361ea audio_id:long caption:PageCaption = PageBlock;
pageBlockKicker#1e148390 text:RichText = PageBlock;
pageBlockTable#bf4dea82 flags:# bordered:flags.0?true striped:flags.1?true title:RichText rows:Vector<PageTableRow> = PageBlock;
pageBlockOrderedList#9a8ae1e1 items:Vector<PageListOrderedItem> = PageBlock;
pageBlockDetails#76768bed flags:# open:flags.0?true blocks:Vector<PageBlock> title:RichText = PageBlock;
pageBlockRelatedArticles#16115a96 title:RichText articles:Vector<PageRelatedArticle> = PageBlock;
pageBlockMap#a44f3ef6 geo:GeoPoint zoom:int w:int h:int caption:PageCaption = PageBlock;

phoneCallDiscardReasonMissed#85e42301 = PhoneCallDiscardReason;
phoneCallDiscardReasonDisconnect#e095c1a0 = PhoneCallDiscardReason;
phoneCallDiscardReasonHangup#57adc690 = PhoneCallDiscardReason;
phoneCallDiscardReasonBusy#faf7e8c9 = PhoneCallDiscardReason;
phoneCallDiscardReasonMigrateConferenceCall#9fbbf1f7 slug:string = PhoneCallDiscardReason;

dataJSON#7d748d04 data:string = DataJSON;

labeledPrice#cb296bf8 label:string amount:long = LabeledPrice;

invoice#49ee584 flags:# test:flags.0?true name_requested:flags.1?true phone_requested:flags.2?true email_requested:flags.3?true shipping_address_requested:flags.4?true flexible:flags.5?true phone_to_provider:flags.6?true email_to_provider:flags.7?true recurring:flags.9?true currency:string prices:Vector<LabeledPrice> max_tip_amount:flags.8?long suggested_tip_amounts:flags.8?Vector<long> terms_url:flags.10?string subscription_period:flags.11?int = Invoice;

paymentCharge#ea02c27e id:string provider_charge_id:string = PaymentCharge;

postAddress#1e8caaeb street_line1:string street_line2:string city:string state:string country_iso2:string post_code:string = PostAddress;

paymentRequestedInfo#909c3f94 flags:# name:flags.0?string phone:flags.1?string email:flags.2?string shipping_address:flags.3?PostAddress = PaymentRequestedInfo;

paymentSavedCredentialsCard#cdc27a1f id:string title:string = PaymentSavedCredentials;

webDocument#1c570ed1 url:string access_hash:long size:int mime_type:string attributes:Vector<DocumentAttribute> = WebDocument;
webDocumentNoProxy#f9c8bcc6 url:string size:int mime_type:string attributes:Vector<DocumentAttribute> = WebDocument;

inputWebDocument#9bed434d url:string size:int mime_type:string attributes:Vector<DocumentAttribute> = InputWebDocument;

inputWebFileLocation#c239d686 url:string access_hash:long = InputWebFileLocation;
inputWebFileGeoPointLocation#9f2221c9 geo_point:InputGeoPoint access_hash:long w:int h:int zoom:int scale:int = InputWebFileLocation;
inputWebFileAudioAlbumThumbLocation#f46fe924 flags:# small:flags.2?true document:flags.0?InputDocument title:flags.1?string performer:flags.1?string = InputWebFileLocation;

upload.webFile#21e753bc size:int mime_type:string file_type:storage.FileType mtime:int bytes:bytes = upload.WebFile;

payments.paymentForm#a0058751 flags:# can_save_credentials:flags.2?true password_missing:flags.3?true form_id:long bot_id:long title:string description:string photo:flags.5?WebDocument invoice:Invoice provider_id:long url:string native_provider:flags.4?string native_params:flags.4?DataJSON additional_methods:flags.6?Vector<PaymentFormMethod> saved_info:flags.0?PaymentRequestedInfo saved_credentials:flags.1?Vector<PaymentSavedCredentials> users:Vector<User> = payments.PaymentForm;
payments.paymentFormStars#7bf6b15c flags:# form_id:long bot_id:long title:string description:string photo:flags.5?WebDocument invoice:Invoice users:Vector<User> = payments.PaymentForm;
payments.paymentFormStarGift#b425cfe1 form_id:long invoice:Invoice = payments.PaymentForm;

payments.validatedRequestedInfo#d1451883 flags:# id:flags.0?string shipping_options:flags.1?Vector<ShippingOption> = payments.ValidatedRequestedInfo;

payments.paymentResult#4e5f810d updates:Updates = payments.PaymentResult;
payments.paymentVerificationNeeded#d8411139 url:string = payments.PaymentResult;

payments.paymentReceipt#70c4fe03 flags:# date:int bot_id:long provider_id:long title:string description:string photo:flags.2?WebDocument invoice:Invoice info:flags.0?PaymentRequestedInfo shipping:flags.1?ShippingOption tip_amount:flags.3?long currency:string total_amount:long credentials_title:string users:Vector<User> = payments.PaymentReceipt;
payments.paymentReceiptStars#dabbf83a flags:# date:int bot_id:long title:string description:string photo:flags.2?WebDocument invoice:Invoice currency:string total_amount:long transaction_id:string users:Vector<User> = payments.PaymentReceipt;

payments.savedInfo#fb8fe43c flags:# has_saved_credentials:flags.1?true saved_info:flags.0?PaymentRequestedInfo = payments.SavedInfo;

inputPaymentCredentialsSaved#c10eb2cf id:string tmp_password:bytes = InputPaymentCredentials;
inputPaymentCredentials#3417d728 flags:# save:flags.0?true data:DataJSON = InputPaymentCredentials;
inputPaymentCredentialsApplePay#aa1c39f payment_data:DataJSON = InputPaymentCredentials;
inputPaymentCredentialsGooglePay#8ac32801 payment_token:DataJSON = InputPaymentCredentials;

account.tmpPassword#db64fd34 tmp_password:bytes valid_until:int = account.TmpPassword;

shippingOption#b6213cdf id:string title:string prices:Vector<LabeledPrice> = ShippingOption;

inputStickerSetItem#32da9e9c flags:# document:InputDocument emoji:string mask_coords:flags.0?MaskCoords keywords:flags.1?string = InputStickerSetItem;

inputPhoneCall#1e36fded id:long access_hash:long = InputPhoneCall;

phoneCallEmpty#5366c915 id:long = PhoneCall;
phoneCallWaiting#c5226f17 flags:# video:flags.6?true id:long access_hash:long date:int admin_id:long participant_id:long protocol:PhoneCallProtocol receive_date:flags.0?int = PhoneCall;
phoneCallRequested#14b0ed0c flags:# video:flags.6?true id:long access_hash:long date:int admin_id:long participant_id:long g_a_hash:bytes protocol:PhoneCallProtocol = PhoneCall;
phoneCallAccepted#3660c311 flags:# video:flags.6?true id:long access_hash:long date:int admin_id:long participant_id:long g_b:bytes protocol:PhoneCallProtocol = PhoneCall;
phoneCall#30535af5 flags:# p2p_allowed:flags.5?true video:flags.6?true conference_supported:flags.8?true id:long access_hash:long date:int admin_id:long participant_id:long g_a_or_b:bytes key_fingerprint:long protocol:PhoneCallProtocol connections:Vector<PhoneConnection> start_date:int custom_parameters:flags.7?DataJSON = PhoneCall;
phoneCallDiscarded#50ca4de1 flags:# need_rating:flags.2?true need_debug:flags.3?true video:flags.6?true id:long reason:flags.0?PhoneCallDiscardReason duration:flags.1?int = PhoneCall;

phoneConnection#9cc123c7 flags:# tcp:flags.0?true id:long ip:string ipv6:string port:int peer_tag:bytes = PhoneConnection;
phoneConnectionWebrtc#635fe375 flags:# turn:flags.0?true stun:flags.1?true id:long ip:string ipv6:string port:int username:string password:string = PhoneConnection;

phoneCallProtocol#fc878fc8 flags:# udp_p2p:flags.0?true udp_reflector:flags.1?true min_layer:int max_layer:int library_versions:Vector<string> = PhoneCallProtocol;

phone.phoneCall#ec82e140 phone_call:PhoneCall users:Vector<User> = phone.PhoneCall;

upload.cdnFileReuploadNeeded#eea8e46e request_token:bytes = upload.CdnFile;
upload.cdnFile#a99fca4f bytes:bytes = upload.CdnFile;

cdnPublicKey#c982eaba dc_id:int public_key:string = CdnPublicKey;

cdnConfig#5725e40a public_keys:Vector<CdnPublicKey> = CdnConfig;

langPackString#cad181f6 key:string value:string = LangPackString;
langPackStringPluralized#6c47ac9f flags:# key:string zero_value:flags.0?string one_value:flags.1?string two_value:flags.2?string few_value:flags.3?string many_value:flags.4?string other_value:string = LangPackString;
langPackStringDeleted#2979eeb2 key:string = LangPackString;

langPackDifference#f385c1f6 lang_code:string from_version:int version:int strings:Vector<LangPackString> = LangPackDifference;

langPackLanguage#eeca5ce3 flags:# official:flags.0?true rtl:flags.2?true beta:flags.3?true name:string native_name:string lang_code:string base_lang_code:flags.1?string plural_code:string strings_count:int translated_count:int translations_url:string = LangPackLanguage;

channelAdminLogEventActionChangeTitle#e6dfb825 prev_value:string new_value:string = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeAbout#55188a2e prev_value:string new_value:string = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeUsername#6a4afc38 prev_value:string new_value:string = ChannelAdminLogEventAction;
channelAdminLogEventActionChangePhoto#434bd2af prev_photo:Photo new_photo:Photo = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleInvites#1b7907ae new_value:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleSignatures#26ae0971 new_value:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionUpdatePinned#e9e82c18 message:Message = ChannelAdminLogEventAction;
channelAdminLogEventActionEditMessage#709b2405 prev_message:Message new_message:Message = ChannelAdminLogEventAction;
channelAdminLogEventActionDeleteMessage#42e047bb message:Message = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantJoin#183040d3 = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantLeave#f89777f2 = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantInvite#e31c34d8 participant:ChannelParticipant = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantToggleBan#e6d83d7e prev_participant:ChannelParticipant new_participant:ChannelParticipant = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantToggleAdmin#d5676710 prev_participant:ChannelParticipant new_participant:ChannelParticipant = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeStickerSet#b1c3caa7 prev_stickerset:InputStickerSet new_stickerset:InputStickerSet = ChannelAdminLogEventAction;
channelAdminLogEventActionTogglePreHistoryHidden#5f5c95f1 new_value:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionDefaultBannedRights#2df5fc0a prev_banned_rights:ChatBannedRights new_banned_rights:ChatBannedRights = ChannelAdminLogEventAction;
channelAdminLogEventActionStopPoll#8f079643 message:Message = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeLinkedChat#50c7ac8 prev_value:long new_value:long = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeLocation#e6b76ae prev_value:ChannelLocation new_value:ChannelLocation = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleSlowMode#53909779 prev_value:int new_value:int = ChannelAdminLogEventAction;
channelAdminLogEventActionStartGroupCall#23209745 call:InputGroupCall = ChannelAdminLogEventAction;
channelAdminLogEventActionDiscardGroupCall#db9f9140 call:InputGroupCall = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantMute#f92424d2 participant:GroupCallParticipant = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantUnmute#e64429c0 participant:GroupCallParticipant = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleGroupCallSetting#56d6a247 join_muted:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantJoinByInvite#fe9fc158 flags:# via_chatlist:flags.0?true invite:ExportedChatInvite = ChannelAdminLogEventAction;
channelAdminLogEventActionExportedInviteDelete#5a50fca4 invite:ExportedChatInvite = ChannelAdminLogEventAction;
channelAdminLogEventActionExportedInviteRevoke#410a134e invite:ExportedChatInvite = ChannelAdminLogEventAction;
channelAdminLogEventActionExportedInviteEdit#e90ebb59 prev_invite:ExportedChatInvite new_invite:ExportedChatInvite = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantVolume#3e7f6847 participant:GroupCallParticipant = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeHistoryTTL#6e941a38 prev_value:int new_value:int = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantJoinByRequest#afb6144a invite:ExportedChatInvite approved_by:long = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleNoForwards#cb2ac766 new_value:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionSendMessage#278f2868 message:Message = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeAvailableReactions#be4e0ef8 prev_value:ChatReactions new_value:ChatReactions = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeUsernames#f04fb3a9 prev_value:Vector<string> new_value:Vector<string> = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleForum#2cc6383 new_value:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionCreateTopic#58707d28 topic:ForumTopic = ChannelAdminLogEventAction;
channelAdminLogEventActionEditTopic#f06fe208 prev_topic:ForumTopic new_topic:ForumTopic = ChannelAdminLogEventAction;
channelAdminLogEventActionDeleteTopic#ae168909 topic:ForumTopic = ChannelAdminLogEventAction;
channelAdminLogEventActionPinTopic#5d8d353b flags:# prev_topic:flags.0?ForumTopic new_topic:flags.1?ForumTopic = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleAntiSpam#64f36dfc new_value:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionChangePeerColor#5796e780 prev_value:PeerColor new_value:PeerColor = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeProfilePeerColor#5e477b25 prev_value:PeerColor new_value:PeerColor = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeWallpaper#31bb5d52 prev_value:WallPaper new_value:WallPaper = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeEmojiStatus#3ea9feb1 prev_value:EmojiStatus new_value:EmojiStatus = ChannelAdminLogEventAction;
channelAdminLogEventActionChangeEmojiStickerSet#46d840ab prev_stickerset:InputStickerSet new_stickerset:InputStickerSet = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleSignatureProfiles#60a79c79 new_value:Bool = ChannelAdminLogEventAction;
channelAdminLogEventActionParticipantSubExtend#64642db3 prev_participant:ChannelParticipant new_participant:ChannelParticipant = ChannelAdminLogEventAction;
channelAdminLogEventActionToggleAutotranslation#c517f77e new_value:Bool = ChannelAdminLogEventAction;

channelAdminLogEvent#1fad68cd id:long date:int user_id:long action:ChannelAdminLogEventAction = ChannelAdminLogEvent;

channels.adminLogResults#ed8af74d events:Vector<ChannelAdminLogEvent> chats:Vector<Chat> users:Vector<User> = channels.AdminLogResults;

channelAdminLogEventsFilter#ea107ae4 flags:# join:flags.0?true leave:flags.1?true invite:flags.2?true ban:flags.3?true unban:flags.4?true kick:flags.5?true unkick:flags.6?true promote:flags.7?true demote:flags.8?true info:flags.9?true settings:flags.10?true pinned:flags.11?true edit:flags.12?true delete:flags.13?true group_call:flags.14?true invites:flags.15?true send:flags.16?true forums:flags.17?true sub_extend:flags.18?true = ChannelAdminLogEventsFilter;

popularContact#5ce14175 client_id:long importers:int = PopularContact;

messages.favedStickersNotModified#9e8fa6d3 = messages.FavedStickers;
messages.favedStickers#2cb51097 hash:long packs:Vector<StickerPack> stickers:Vector<Document> = messages.FavedStickers;

recentMeUrlUnknown#46e1d13d url:string = RecentMeUrl;
recentMeUrlUser#b92c09e2 url:string user_id:long = RecentMeUrl;
recentMeUrlChat#b2da71d2 url:string chat_id:long = RecentMeUrl;
recentMeUrlChatInvite#eb49081d url:string chat_invite:ChatInvite = RecentMeUrl;
recentMeUrlStickerSet#bc0a57dc url:string set:StickerSetCovered = RecentMeUrl;

help.recentMeUrls#e0310d7 urls:Vector<RecentMeUrl> chats:Vector<Chat> users:Vector<User> = help.RecentMeUrls;

inputSingleMedia#1cc6e91f flags:# media:InputMedia random_id:long message:string entities:flags.0?Vector<MessageEntity> = InputSingleMedia;

webAuthorization#a6f8f452 hash:long bot_id:long domain:string browser:string platform:string date_created:int date_active:int ip:string region:string = WebAuthorization;

account.webAuthorizations#ed56c9fc authorizations:Vector<WebAuthorization> users:Vector<User> = account.WebAuthorizations;

inputMessageID#a676a322 id:int = InputMessage;
inputMessageReplyTo#bad88395 id:int = InputMessage;
inputMessagePinned#86872538 = InputMessage;
inputMessageCallbackQuery#acfa1a7e id:int query_id:long = InputMessage;

inputDialogPeer#fcaafeb7 peer:InputPeer = InputDialogPeer;
inputDialogPeerFolder#64600527 folder_id:int = InputDialogPeer;

dialogPeer#e56dbf05 peer:Peer = DialogPeer;
dialogPeerFolder#514519e2 folder_id:int = DialogPeer;

messages.foundStickerSetsNotModified#d54b65d = messages.FoundStickerSets;
messages.foundStickerSets#8af09dd2 hash:long sets:Vector<StickerSetCovered> = messages.FoundStickerSets;

fileHash#f39b035c offset:long limit:int hash:bytes = FileHash;

inputClientProxy#75588b3f address:string port:int = InputClientProxy;

help.termsOfServiceUpdateEmpty#e3309f7f expires:int = help.TermsOfServiceUpdate;
help.termsOfServiceUpdate#28ecf961 expires:int terms_of_service:help.TermsOfService = help.TermsOfServiceUpdate;

inputSecureFileUploaded#3334b0f0 id:long parts:int md5_checksum:string file_hash:bytes secret:bytes = InputSecureFile;
inputSecureFile#5367e5be id:long access_hash:long = InputSecureFile;

secureFileEmpty#64199744 = SecureFile;
secureFile#7d09c27e id:long access_hash:long size:long dc_id:int date:int file_hash:bytes secret:bytes = SecureFile;

secureData#8aeabec3 data:bytes data_hash:bytes secret:bytes = SecureData;

securePlainPhone#7d6099dd phone:string = SecurePlainData;
securePlainEmail#21ec5a5f email:string = SecurePlainData;

secureValueTypePersonalDetails#9d2a81e3 = SecureValueType;
secureValueTypePassport#3dac6a00 = SecureValueType;
secureValueTypeDriverLicense#6e425c4 = SecureValueType;
secureValueTypeIdentityCard#a0d0744b = SecureValueType;
secureValueTypeInternalPassport#99a48f23 = SecureValueType;
secureValueTypeAddress#cbe31e26 = SecureValueType;
secureValueTypeUtilityBill#fc36954e = SecureValueType;
secureValueTypeBankStatement#89137c0d = SecureValueType;
secureValueTypeRentalAgreement#8b883488 = SecureValueType;
secureValueTypePassportRegistration#99e3806a = SecureValueType;
secureValueTypeTemporaryRegistration#ea02ec33 = SecureValueType;
secureValueTypePhone#b320aadb = SecureValueType;
secureValueTypeEmail#8e3ca7ee = SecureValueType;

secureValue#187fa0ca flags:# type:SecureValueType data:flags.0?SecureData front_side:flags.1?SecureFile reverse_side:flags.2?SecureFile selfie:flags.3?SecureFile translation:flags.6?Vector<SecureFile> files:flags.4?Vector<SecureFile> plain_data:flags.5?SecurePlainData hash:bytes = SecureValue;

inputSecureValue#db21d0a7 flags:# type:SecureValueType data:flags.0?SecureData front_side:flags.1?InputSecureFile reverse_side:flags.2?InputSecureFile selfie:flags.3?InputSecureFile translation:flags.6?Vector<InputSecureFile> files:flags.4?Vector<InputSecureFile> plain_data:flags.5?SecurePlainData = InputSecureValue;

secureValueHash#ed1ecdb0 type:SecureValueType hash:bytes = SecureValueHash;

secureValueErrorData#e8a40bd9 type:SecureValueType data_hash:bytes field:string text:string = SecureValueError;
secureValueErrorFrontSide#be3dfa type:SecureValueType file_hash:bytes text:string = SecureValueError;
secureValueErrorReverseSide#868a2aa5 type:SecureValueType file_hash:bytes text:string = SecureValueError;
secureValueErrorSelfie#e537ced6 type:SecureValueType file_hash:bytes text:string = SecureValueError;
secureValueErrorFile#7a700873 type:SecureValueType file_hash:bytes text:string = SecureValueError;
secureValueErrorFiles#666220e9 type:SecureValueType file_hash:Vector<bytes> text:string = SecureValueError;
secureValueError#869d758f type:SecureValueType hash:bytes text:string = SecureValueError;
secureValueErrorTranslationFile#a1144770 type:SecureValueType file_hash:bytes text:string = SecureValueError;
secureValueErrorTranslationFiles#34636dd8 type:SecureValueType file_hash:Vector<bytes> text:string = SecureValueError;

secureCredentialsEncrypted#33f0ea47 data:bytes hash:bytes secret:bytes = SecureCredentialsEncrypted;

account.authorizationForm#ad2e1cd8 flags:# required_types:Vector<SecureRequiredType> values:Vector<SecureValue> errors:Vector<SecureValueError> users:Vector<User> privacy_policy_url:flags.0?string = account.AuthorizationForm;

account.sentEmailCode#811f854f email_pattern:string length:int = account.SentEmailCode;

help.deepLinkInfoEmpty#66afa166 = help.DeepLinkInfo;
help.deepLinkInfo#6a4ee832 flags:# update_app:flags.0?true message:string entities:flags.1?Vector<MessageEntity> = help.DeepLinkInfo;

savedPhoneContact#1142bd56 phone:string first_name:string last_name:string date:int = SavedContact;

account.takeout#4dba4501 id:long = account.Takeout;

passwordKdfAlgoUnknown#d45ab096 = PasswordKdfAlgo;
passwordKdfAlgoSHA256SHA256PBKDF2HMACSHA512iter100000SHA256ModPow#3a912d4a salt1:bytes salt2:bytes g:int p:bytes = PasswordKdfAlgo;

securePasswordKdfAlgoUnknown#4a8537 = SecurePasswordKdfAlgo;
securePasswordKdfAlgoPBKDF2HMACSHA512iter100000#bbf2dda0 salt:bytes = SecurePasswordKdfAlgo;
securePasswordKdfAlgoSHA512#86471d92 salt:bytes = SecurePasswordKdfAlgo;

secureSecretSettings#1527bcac secure_algo:SecurePasswordKdfAlgo secure_secret:bytes secure_secret_id:long = SecureSecretSettings;

inputCheckPasswordEmpty#9880f658 = InputCheckPasswordSRP;
inputCheckPasswordSRP#d27ff082 srp_id:long A:bytes M1:bytes = InputCheckPasswordSRP;

secureRequiredType#829d99da flags:# native_names:flags.0?true selfie_required:flags.1?true translation_required:flags.2?true type:SecureValueType = SecureRequiredType;
secureRequiredTypeOneOf#27477b4 types:Vector<SecureRequiredType> = SecureRequiredType;

help.passportConfigNotModified#bfb9f457 = help.PassportConfig;
help.passportConfig#a098d6af hash:int countries_langs:DataJSON = help.PassportConfig;

inputAppEvent#1d1b1245 time:double type:string peer:long data:JSONValue = InputAppEvent;

jsonObjectValue#c0de1bd9 key:string value:JSONValue = JSONObjectValue;

jsonNull#3f6d7b68 = JSONValue;
jsonBool#c7345e6a value:Bool = JSONValue;
jsonNumber#2be0dfa4 value:double = JSONValue;
jsonString#b71e767a value:string = JSONValue;
jsonArray#f7444763 value:Vector<JSONValue> = JSONValue;
jsonObject#99c1d49d value:Vector<JSONObjectValue> = JSONValue;

pageTableCell#34566b6a flags:# header:flags.0?true align_center:flags.3?true align_right:flags.4?true valign_middle:flags.5?true valign_bottom:flags.6?true text:flags.7?RichText colspan:flags.1?int rowspan:flags.2?int = PageTableCell;

pageTableRow#e0c0c5e5 cells:Vector<PageTableCell> = PageTableRow;

pageCaption#6f747657 text:RichText credit:RichText = PageCaption;

pageListItemText#b92fb6cd text:RichText = PageListItem;
pageListItemBlocks#25e073fc blocks:Vector<PageBlock> = PageListItem;

pageListOrderedItemText#5e068047 num:string text:RichText = PageListOrderedItem;
pageListOrderedItemBlocks#98dd8936 num:string blocks:Vector<PageBlock> = PageListOrderedItem;

pageRelatedArticle#b390dc08 flags:# url:string webpage_id:long title:flags.0?string description:flags.1?string photo_id:flags.2?long author:flags.3?string published_date:flags.4?int = PageRelatedArticle;

page#98657f0d flags:# part:flags.0?true rtl:flags.1?true v2:flags.2?true url:string blocks:Vector<PageBlock> photos:Vector<Photo> documents:Vector<Document> views:flags.3?int = Page;

help.supportName#8c05f1c9 name:string = help.SupportName;

help.userInfoEmpty#f3ae2eed = help.UserInfo;
help.userInfo#1eb3758 message:string entities:Vector<MessageEntity> author:string date:int = help.UserInfo;

pollAnswer#ff16e2ca text:TextWithEntities option:bytes = PollAnswer;

poll#58747131 id:long flags:# closed:flags.0?true public_voters:flags.1?true multiple_choice:flags.2?true quiz:flags.3?true question:TextWithEntities answers:Vector<PollAnswer> close_period:flags.4?int close_date:flags.5?int = Poll;

pollAnswerVoters#3b6ddad2 flags:# chosen:flags.0?true correct:flags.1?true option:bytes voters:int = PollAnswerVoters;

pollResults#7adf2420 flags:# min:flags.0?true results:flags.1?Vector<PollAnswerVoters> total_voters:flags.2?int recent_voters:flags.3?Vector<Peer> solution:flags.4?string solution_entities:flags.4?Vector<MessageEntity> = PollResults;

chatOnlines#f041e250 onlines:int = ChatOnlines;

statsURL#47a971e0 url:string = StatsURL;

chatAdminRights#5fb224d5 flags:# change_info:flags.0?true post_messages:flags.1?true edit_messages:flags.2?true delete_messages:flags.3?true ban_users:flags.4?true invite_users:flags.5?true pin_messages:flags.7?true add_admins:flags.9?true anonymous:flags.10?true manage_call:flags.11?true other:flags.12?true manage_topics:flags.13?true post_stories:flags.14?true edit_stories:flags.15?true delete_stories:flags.16?true manage_direct_messages:flags.17?true = ChatAdminRights;

chatBannedRights#9f120418 flags:# view_messages:flags.0?true send_messages:flags.1?true send_media:flags.2?true send_stickers:flags.3?true send_gifs:flags.4?true send_games:flags.5?true send_inline:flags.6?true embed_links:flags.7?true send_polls:flags.8?true change_info:flags.10?true invite_users:flags.15?true pin_messages:flags.17?true manage_topics:flags.18?true send_photos:flags.19?true send_videos:flags.20?true send_roundvideos:flags.21?true send_audios:flags.22?true send_voices:flags.23?true send_docs:flags.24?true send_plain:flags.25?true until_date:int = ChatBannedRights;

inputWallPaper#e630b979 id:long access_hash:long = InputWallPaper;
inputWallPaperSlug#72091c80 slug:string = InputWallPaper;
inputWallPaperNoFile#967a462e id:long = InputWallPaper;

account.wallPapersNotModified#1c199183 = account.WallPapers;
account.wallPapers#cdc3858c hash:long wallpapers:Vector<WallPaper> = account.WallPapers;

codeSettings#ad253d78 flags:# allow_flashcall:flags.0?true current_number:flags.1?true allow_app_hash:flags.4?true allow_missed_call:flags.5?true allow_firebase:flags.7?true unknown_number:flags.9?true logout_tokens:flags.6?Vector<bytes> token:flags.8?string app_sandbox:flags.8?Bool = CodeSettings;

wallPaperSettings#372efcd0 flags:# blur:flags.1?true motion:flags.2?true background_color:flags.0?int second_background_color:flags.4?int third_background_color:flags.5?int fourth_background_color:flags.6?int intensity:flags.3?int rotation:flags.4?int emoticon:flags.7?string = WallPaperSettings;

autoDownloadSettings#baa57628 flags:# disabled:flags.0?true video_preload_large:flags.1?true audio_preload_next:flags.2?true phonecalls_less_data:flags.3?true stories_preload:flags.4?true photo_size_max:int video_size_max:long file_size_max:long video_upload_maxbitrate:int small_queue_active_operations_max:int large_queue_active_operations_max:int = AutoDownloadSettings;

account.autoDownloadSettings#63cacf26 low:AutoDownloadSettings medium:AutoDownloadSettings high:AutoDownloadSettings = account.AutoDownloadSettings;

emojiKeyword#d5b3b9f9 keyword:string emoticons:Vector<string> = EmojiKeyword;
emojiKeywordDeleted#236df622 keyword:string emoticons:Vector<string> = EmojiKeyword;

emojiKeywordsDifference#5cc761bd lang_code:string from_version:int version:int keywords:Vector<EmojiKeyword> = EmojiKeywordsDifference;

emojiURL#a575739d url:string = EmojiURL;

emojiLanguage#b3fb5361 lang_code:string = EmojiLanguage;

folder#ff544e65 flags:# autofill_new_broadcasts:flags.0?true autofill_public_groups:flags.1?true autofill_new_correspondents:flags.2?true id:int title:string photo:flags.3?ChatPhoto = Folder;

inputFolderPeer#fbd2c296 peer:InputPeer folder_id:int = InputFolderPeer;

folderPeer#e9baa668 peer:Peer folder_id:int = FolderPeer;

messages.searchCounter#e844ebff flags:# inexact:flags.1?true filter:MessagesFilter count:int = messages.SearchCounter;

urlAuthResultRequest#92d33a0e flags:# request_write_access:flags.0?true bot:User domain:string = UrlAuthResult;
urlAuthResultAccepted#8f8c0e4e url:string = UrlAuthResult;
urlAuthResultDefault#a9d6db1f = UrlAuthResult;

channelLocationEmpty#bfb5ad8b = ChannelLocation;
channelLocation#209b82db geo_point:GeoPoint address:string = ChannelLocation;

peerLocated#ca461b5d peer:Peer expires:int distance:int = PeerLocated;
peerSelfLocated#f8ec284b expires:int = PeerLocated;

restrictionReason#d072acb4 platform:string reason:string text:string = RestrictionReason;

inputTheme#3c5693e9 id:long access_hash:long = InputTheme;
inputThemeSlug#f5890df1 slug:string = InputTheme;

theme#a00e67d6 flags:# creator:flags.0?true default:flags.1?true for_chat:flags.5?true id:long access_hash:long slug:string title:string document:flags.2?Document settings:flags.3?Vector<ThemeSettings> emoticon:flags.6?string installs_count:flags.4?int = Theme;

account.themesNotModified#f41eb622 = account.Themes;
account.themes#9a3d8c6d hash:long themes:Vector<Theme> = account.Themes;

auth.loginToken#629f1980 expires:int token:bytes = auth.LoginToken;
auth.loginTokenMigrateTo#68e9916 dc_id:int token:bytes = auth.LoginToken;
auth.loginTokenSuccess#390d5c5e authorization:auth.Authorization = auth.LoginToken;

account.contentSettings#57e28221 flags:# sensitive_enabled:flags.0?true sensitive_can_change:flags.1?true = account.ContentSettings;

messages.inactiveChats#a927fec5 dates:Vector<int> chats:Vector<Chat> users:Vector<User> = messages.InactiveChats;

baseThemeClassic#c3a12462 = BaseTheme;
baseThemeDay#fbd81688 = BaseTheme;
baseThemeNight#b7b31ea8 = BaseTheme;
baseThemeTinted#6d5f77ee = BaseTheme;
baseThemeArctic#5b11125a = BaseTheme;

inputThemeSettings#8fde504f flags:# message_colors_animated:flags.2?true base_theme:BaseTheme accent_color:int outbox_accent_color:flags.3?int message_colors:flags.0?Vector<int> wallpaper:flags.1?InputWallPaper wallpaper_settings:flags.1?WallPaperSettings = InputThemeSettings;

themeSettings#fa58b6d4 flags:# message_colors_animated:flags.2?true base_theme:BaseTheme accent_color:int outbox_accent_color:flags.3?int message_colors:flags.0?Vector<int> wallpaper:flags.1?WallPaper = ThemeSettings;

webPageAttributeTheme#54b56617 flags:# documents:flags.0?Vector<Document> settings:flags.1?ThemeSettings = WebPageAttribute;
webPageAttributeStory#2e94c3e7 flags:# peer:Peer id:int story:flags.0?StoryItem = WebPageAttribute;
webPageAttributeStickerSet#50cc03d3 flags:# emojis:flags.0?true text_color:flags.1?true stickers:Vector<Document> = WebPageAttribute;
webPageAttributeUniqueStarGift#cf6f6db8 gift:StarGift = WebPageAttribute;
webPageAttributeStarGiftCollection#31cad303 icons:Vector<Document> = WebPageAttribute;

messages.votesList#4899484e flags:# count:int votes:Vector<MessagePeerVote> chats:Vector<Chat> users:Vector<User> next_offset:flags.0?string = messages.VotesList;

bankCardOpenUrl#f568028a url:string name:string = BankCardOpenUrl;

payments.bankCardData#3e24e573 title:string open_urls:Vector<BankCardOpenUrl> = payments.BankCardData;

dialogFilter#aa472651 flags:# contacts:flags.0?true non_contacts:flags.1?true groups:flags.2?true broadcasts:flags.3?true bots:flags.4?true exclude_muted:flags.11?true exclude_read:flags.12?true exclude_archived:flags.13?true title_noanimate:flags.28?true id:int title:TextWithEntities emoticon:flags.25?string color:flags.27?int pinned_peers:Vector<InputPeer> include_peers:Vector<InputPeer> exclude_peers:Vector<InputPeer> = DialogFilter;
dialogFilterDefault#363293ae = DialogFilter;
dialogFilterChatlist#96537bd7 flags:# has_my_invites:flags.26?true title_noanimate:flags.28?true id:int title:TextWithEntities emoticon:flags.25?string color:flags.27?int pinned_peers:Vector<InputPeer> include_peers:Vector<InputPeer> = DialogFilter;

dialogFilterSuggested#77744d4a filter:DialogFilter description:string = DialogFilterSuggested;

statsDateRangeDays#b637edaf min_date:int max_date:int = StatsDateRangeDays;

statsAbsValueAndPrev#cb43acde current:double previous:double = StatsAbsValueAndPrev;

statsPercentValue#cbce2fe0 part:double total:double = StatsPercentValue;

statsGraphAsync#4a27eb2d token:string = StatsGraph;
statsGraphError#bedc9822 error:string = StatsGraph;
statsGraph#8ea464b6 flags:# json:DataJSON zoom_token:flags.0?string = StatsGraph;

stats.broadcastStats#396ca5fc period:StatsDateRangeDays followers:StatsAbsValueAndPrev views_per_post:StatsAbsValueAndPrev shares_per_post:StatsAbsValueAndPrev reactions_per_post:StatsAbsValueAndPrev views_per_story:StatsAbsValueAndPrev shares_per_story:StatsAbsValueAndPrev reactions_per_story:StatsAbsValueAndPrev enabled_notifications:StatsPercentValue growth_graph:StatsGraph followers_graph:StatsGraph mute_graph:StatsGraph top_hours_graph:StatsGraph interactions_graph:StatsGraph iv_interactions_graph:StatsGraph views_by_source_graph:StatsGraph new_followers_by_source_graph:StatsGraph languages_graph:StatsGraph reactions_by_emotion_graph:StatsGraph story_interactions_graph:StatsGraph story_reactions_by_emotion_graph:StatsGraph recent_posts_interactions:Vector<PostInteractionCounters> = stats.BroadcastStats;

help.promoDataEmpty#98f6ac75 expires:int = help.PromoData;
help.promoData#8a4d87a flags:# proxy:flags.0?true expires:int peer:flags.3?Peer psa_type:flags.1?string psa_message:flags.2?string pending_suggestions:Vector<string> dismissed_suggestions:Vector<string> custom_pending_suggestion:flags.4?PendingSuggestion chats:Vector<Chat> users:Vector<User> = help.PromoData;

videoSize#de33b094 flags:# type:string w:int h:int size:int video_start_ts:flags.0?double = VideoSize;
videoSizeEmojiMarkup#f85c413c emoji_id:long background_colors:Vector<int> = VideoSize;
videoSizeStickerMarkup#da082fe stickerset:InputStickerSet sticker_id:long background_colors:Vector<int> = VideoSize;

statsGroupTopPoster#9d04af9b user_id:long messages:int avg_chars:int = StatsGroupTopPoster;

statsGroupTopAdmin#d7584c87 user_id:long deleted:int kicked:int banned:int = StatsGroupTopAdmin;

statsGroupTopInviter#535f779d user_id:long invitations:int = StatsGroupTopInviter;

stats.megagroupStats#ef7ff916 period:StatsDateRangeDays members:StatsAbsValueAndPrev messages:StatsAbsValueAndPrev viewers:StatsAbsValueAndPrev posters:StatsAbsValueAndPrev growth_graph:StatsGraph members_graph:StatsGraph new_members_by_source_graph:StatsGraph languages_graph:StatsGraph messages_graph:StatsGraph actions_graph:StatsGraph top_hours_graph:StatsGraph weekdays_graph:StatsGraph top_posters:Vector<StatsGroupTopPoster> top_admins:Vector<StatsGroupTopAdmin> top_inviters:Vector<StatsGroupTopInviter> users:Vector<User> = stats.MegagroupStats;

globalPrivacySettings#fe41b34f flags:# archive_and_mute_new_noncontact_peers:flags.0?true keep_archived_unmuted:flags.1?true keep_archived_folders:flags.2?true hide_read_marks:flags.3?true new_noncontact_peers_require_premium:flags.4?true display_gifts_button:flags.7?true noncontact_peers_paid_stars:flags.5?long disallowed_gifts:flags.6?DisallowedGiftsSettings = GlobalPrivacySettings;

help.countryCode#4203c5ef flags:# country_code:string prefixes:flags.0?Vector<string> patterns:flags.1?Vector<string> = help.CountryCode;

help.country#c3878e23 flags:# hidden:flags.0?true iso2:string default_name:string name:flags.1?string country_codes:Vector<help.CountryCode> = help.Country;

help.countriesListNotModified#93cc1f32 = help.CountriesList;
help.countriesList#87d0759e countries:Vector<help.Country> hash:int = help.CountriesList;

messageViews#455b853d flags:# views:flags.0?int forwards:flags.1?int replies:flags.2?MessageReplies = MessageViews;

messages.messageViews#b6c4f543 views:Vector<MessageViews> chats:Vector<Chat> users:Vector<User> = messages.MessageViews;

messages.discussionMessage#a6341782 flags:# messages:Vector<Message> max_id:flags.0?int read_inbox_max_id:flags.1?int read_outbox_max_id:flags.2?int unread_count:int chats:Vector<Chat> users:Vector<User> = messages.DiscussionMessage;

messageReplyHeader#6917560b flags:# reply_to_scheduled:flags.2?true forum_topic:flags.3?true quote:flags.9?true reply_to_msg_id:flags.4?int reply_to_peer_id:flags.0?Peer reply_from:flags.5?MessageFwdHeader reply_media:flags.8?MessageMedia reply_to_top_id:flags.1?int quote_text:flags.6?string quote_entities:flags.7?Vector<MessageEntity> quote_offset:flags.10?int todo_item_id:flags.11?int = MessageReplyHeader;
messageReplyStoryHeader#e5af939 peer:Peer story_id:int = MessageReplyHeader;

messageReplies#83d60fc2 flags:# comments:flags.0?true replies:int replies_pts:int recent_repliers:flags.1?Vector<Peer> channel_id:flags.0?long max_id:flags.2?int read_max_id:flags.3?int = MessageReplies;

peerBlocked#e8fd8014 peer_id:Peer date:int = PeerBlocked;

stats.messageStats#7fe91c14 views_graph:StatsGraph reactions_by_emotion_graph:StatsGraph = stats.MessageStats;

groupCallDiscarded#7780bcb4 id:long access_hash:long duration:int = GroupCall;
groupCall#553b0ba1 flags:# join_muted:flags.1?true can_change_join_muted:flags.2?true join_date_asc:flags.6?true schedule_start_subscribed:flags.8?true can_start_video:flags.9?true record_video_active:flags.11?true rtmp_stream:flags.12?true listeners_hidden:flags.13?true conference:flags.14?true creator:flags.15?true id:long access_hash:long participants_count:int title:flags.3?string stream_dc_id:flags.4?int record_start_date:flags.5?int schedule_date:flags.7?int unmuted_video_count:flags.10?int unmuted_video_limit:int version:int invite_link:flags.16?string = GroupCall;

inputGroupCall#d8aa840f id:long access_hash:long = InputGroupCall;
inputGroupCallSlug#fe06823f slug:string = InputGroupCall;
inputGroupCallInviteMessage#8c10603f msg_id:int = InputGroupCall;

groupCallParticipant#eba636fe flags:# muted:flags.0?true left:flags.1?true can_self_unmute:flags.2?true just_joined:flags.4?true versioned:flags.5?true min:flags.8?true muted_by_you:flags.9?true volume_by_admin:flags.10?true self:flags.12?true video_joined:flags.15?true peer:Peer date:int active_date:flags.3?int source:int volume:flags.7?int about:flags.11?string raise_hand_rating:flags.13?long video:flags.6?GroupCallParticipantVideo presentation:flags.14?GroupCallParticipantVideo = GroupCallParticipant;

phone.groupCall#9e727aad call:GroupCall participants:Vector<GroupCallParticipant> participants_next_offset:string chats:Vector<Chat> users:Vector<User> = phone.GroupCall;

phone.groupParticipants#f47751b6 count:int participants:Vector<GroupCallParticipant> next_offset:string chats:Vector<Chat> users:Vector<User> version:int = phone.GroupParticipants;

inlineQueryPeerTypeSameBotPM#3081ed9d = InlineQueryPeerType;
inlineQueryPeerTypePM#833c0fac = InlineQueryPeerType;
inlineQueryPeerTypeChat#d766c50a = InlineQueryPeerType;
inlineQueryPeerTypeMegagroup#5ec4be43 = InlineQueryPeerType;
inlineQueryPeerTypeBroadcast#6334ee9a = InlineQueryPeerType;
inlineQueryPeerTypeBotPM#e3b2d0c = InlineQueryPeerType;

messages.historyImport#1662af0b id:long = messages.HistoryImport;

messages.historyImportParsed#5e0fb7b9 flags:# pm:flags.0?true group:flags.1?true title:flags.2?string = messages.HistoryImportParsed;

messages.affectedFoundMessages#ef8d3e6c pts:int pts_count:int offset:int messages:Vector<int> = messages.AffectedFoundMessages;

chatInviteImporter#8c5adfd9 flags:# requested:flags.0?true via_chatlist:flags.3?true user_id:long date:int about:flags.2?string approved_by:flags.1?long = ChatInviteImporter;

messages.exportedChatInvites#bdc62dcc count:int invites:Vector<ExportedChatInvite> users:Vector<User> = messages.ExportedChatInvites;

messages.exportedChatInvite#1871be50 invite:ExportedChatInvite users:Vector<User> = messages.ExportedChatInvite;
messages.exportedChatInviteReplaced#222600ef invite:ExportedChatInvite new_invite:ExportedChatInvite users:Vector<User> = messages.ExportedChatInvite;

messages.chatInviteImporters#81b6b00a count:int importers:Vector<ChatInviteImporter> users:Vector<User> = messages.ChatInviteImporters;

chatAdminWithInvites#f2ecef23 admin_id:long invites_count:int revoked_invites_count:int = ChatAdminWithInvites;

messages.chatAdminsWithInvites#b69b72d7 admins:Vector<ChatAdminWithInvites> users:Vector<User> = messages.ChatAdminsWithInvites;

messages.checkedHistoryImportPeer#a24de717 confirm_text:string = messages.CheckedHistoryImportPeer;

phone.joinAsPeers#afe5623f peers:Vector<Peer> chats:Vector<Chat> users:Vector<User> = phone.JoinAsPeers;

phone.exportedGroupCallInvite#204bd158 link:string = phone.ExportedGroupCallInvite;

groupCallParticipantVideoSourceGroup#dcb118b7 semantics:string sources:Vector<int> = GroupCallParticipantVideoSourceGroup;

groupCallParticipantVideo#67753ac8 flags:# paused:flags.0?true endpoint:string source_groups:Vector<GroupCallParticipantVideoSourceGroup> audio_source:flags.1?int = GroupCallParticipantVideo;

stickers.suggestedShortName#85fea03f short_name:string = stickers.SuggestedShortName;

botCommandScopeDefault#2f6cb2ab = BotCommandScope;
botCommandScopeUsers#3c4f04d8 = BotCommandScope;
botCommandScopeChats#6fe1a881 = BotCommandScope;
botCommandScopeChatAdmins#b9aa606a = BotCommandScope;
botCommandScopePeer#db9d897d peer:InputPeer = BotCommandScope;
botCommandScopePeerAdmins#3fd863d1 peer:InputPeer = BotCommandScope;
botCommandScopePeerUser#a1321f3 peer:InputPeer user_id:InputUser = BotCommandScope;

account.resetPasswordFailedWait#e3779861 retry_date:int = account.ResetPasswordResult;
account.resetPasswordRequestedWait#e9effc7d until_date:int = account.ResetPasswordResult;
account.resetPasswordOk#e926d63e = account.ResetPasswordResult;

chatTheme#c3dffc04 emoticon:string = ChatTheme;
chatThemeUniqueGift#3458f9c8 gift:StarGift theme_settings:Vector<ThemeSettings> = ChatTheme;

account.chatThemesNotModified#e011e1c4 = account.ChatThemes;
account.chatThemes#16484857 flags:# hash:long themes:Vector<ChatTheme> chats:Vector<Chat> users:Vector<User> next_offset:flags.0?int = account.ChatThemes;

sponsoredMessage#7dbf8673 flags:# recommended:flags.5?true can_report:flags.12?true random_id:bytes url:string title:string message:string entities:flags.1?Vector<MessageEntity> photo:flags.6?Photo media:flags.14?MessageMedia color:flags.13?PeerColor button_text:string sponsor_info:flags.7?string additional_info:flags.8?string min_display_duration:flags.15?int max_display_duration:flags.15?int = SponsoredMessage;

messages.sponsoredMessages#ffda656d flags:# posts_between:flags.0?int start_delay:flags.1?int between_delay:flags.2?int messages:Vector<SponsoredMessage> chats:Vector<Chat> users:Vector<User> = messages.SponsoredMessages;
messages.sponsoredMessagesEmpty#1839490f = messages.SponsoredMessages;

searchResultsCalendarPeriod#c9b0539f date:int min_msg_id:int max_msg_id:int count:int = SearchResultsCalendarPeriod;

messages.searchResultsCalendar#147ee23c flags:# inexact:flags.0?true count:int min_date:int min_msg_id:int offset_id_offset:flags.1?int periods:Vector<SearchResultsCalendarPeriod> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.SearchResultsCalendar;

searchResultPosition#7f648b67 msg_id:int date:int offset:int = SearchResultsPosition;

messages.searchResultsPositions#53b22baf count:int positions:Vector<SearchResultsPosition> = messages.SearchResultsPositions;

channels.sendAsPeers#f496b0c6 peers:Vector<SendAsPeer> chats:Vector<Chat> users:Vector<User> = channels.SendAsPeers;

users.userFull#3b6d152e full_user:UserFull chats:Vector<Chat> users:Vector<User> = users.UserFull;

messages.peerSettings#6880b94d settings:PeerSettings chats:Vector<Chat> users:Vector<User> = messages.PeerSettings;

auth.loggedOut#c3a2835f flags:# future_auth_token:flags.0?bytes = auth.LoggedOut;

reactionCount#a3d1cb80 flags:# chosen_order:flags.0?int reaction:Reaction count:int = ReactionCount;

messageReactions#a339f0b flags:# min:flags.0?true can_see_list:flags.2?true reactions_as_tags:flags.3?true results:Vector<ReactionCount> recent_reactions:flags.1?Vector<MessagePeerReaction> top_reactors:flags.4?Vector<MessageReactor> = MessageReactions;

messages.messageReactionsList#31bd492d flags:# count:int reactions:Vector<MessagePeerReaction> chats:Vector<Chat> users:Vector<User> next_offset:flags.0?string = messages.MessageReactionsList;

availableReaction#c077ec01 flags:# inactive:flags.0?true premium:flags.2?true reaction:string title:string static_icon:Document appear_animation:Document select_animation:Document activate_animation:Document effect_animation:Document around_animation:flags.1?Document center_icon:flags.1?Document = AvailableReaction;

messages.availableReactionsNotModified#9f071957 = messages.AvailableReactions;
messages.availableReactions#768e3aad hash:int reactions:Vector<AvailableReaction> = messages.AvailableReactions;

messagePeerReaction#8c79b63c flags:# big:flags.0?true unread:flags.1?true my:flags.2?true peer_id:Peer date:int reaction:Reaction = MessagePeerReaction;

groupCallStreamChannel#80eb48af channel:int scale:int last_timestamp_ms:long = GroupCallStreamChannel;

phone.groupCallStreamChannels#d0e482b2 channels:Vector<GroupCallStreamChannel> = phone.GroupCallStreamChannels;

phone.groupCallStreamRtmpUrl#2dbf3432 url:string key:string = phone.GroupCallStreamRtmpUrl;

attachMenuBotIconColor#4576f3f0 name:string color:int = AttachMenuBotIconColor;

attachMenuBotIcon#b2a7386b flags:# name:string icon:Document colors:flags.0?Vector<AttachMenuBotIconColor> = AttachMenuBotIcon;

attachMenuBot#d90d8dfe flags:# inactive:flags.0?true has_settings:flags.1?true request_write_access:flags.2?true show_in_attach_menu:flags.3?true show_in_side_menu:flags.4?true side_menu_disclaimer_needed:flags.5?true bot_id:long short_name:string peer_types:flags.3?Vector<AttachMenuPeerType> icons:Vector<AttachMenuBotIcon> = AttachMenuBot;

attachMenuBotsNotModified#f1d88a5c = AttachMenuBots;
attachMenuBots#3c4301c0 hash:long bots:Vector<AttachMenuBot> users:Vector<User> = AttachMenuBots;

attachMenuBotsBot#93bf667f bot:AttachMenuBot users:Vector<User> = AttachMenuBotsBot;

webViewResultUrl#4d22ff98 flags:# fullsize:flags.1?true fullscreen:flags.2?true query_id:flags.0?long url:string = WebViewResult;

webViewMessageSent#c94511c flags:# msg_id:flags.0?InputBotInlineMessageID = WebViewMessageSent;

botMenuButtonDefault#7533a588 = BotMenuButton;
botMenuButtonCommands#4258c205 = BotMenuButton;
botMenuButton#c7b57ce6 text:string url:string = BotMenuButton;

account.savedRingtonesNotModified#fbf6e8b1 = account.SavedRingtones;
account.savedRingtones#c1e92cc5 hash:long ringtones:Vector<Document> = account.SavedRingtones;

notificationSoundDefault#97e8bebe = NotificationSound;
notificationSoundNone#6f0c34df = NotificationSound;
notificationSoundLocal#830b9ae4 title:string data:string = NotificationSound;
notificationSoundRingtone#ff6c8049 id:long = NotificationSound;

account.savedRingtone#b7263f6d = account.SavedRingtone;
account.savedRingtoneConverted#1f307eb7 document:Document = account.SavedRingtone;

attachMenuPeerTypeSameBotPM#7d6be90e = AttachMenuPeerType;
attachMenuPeerTypeBotPM#c32bfa1a = AttachMenuPeerType;
attachMenuPeerTypePM#f146d31f = AttachMenuPeerType;
attachMenuPeerTypeChat#509113f = AttachMenuPeerType;
attachMenuPeerTypeBroadcast#7bfbdefc = AttachMenuPeerType;

inputInvoiceMessage#c5b56859 peer:InputPeer msg_id:int = InputInvoice;
inputInvoiceSlug#c326caef slug:string = InputInvoice;
inputInvoicePremiumGiftCode#98986c0d purpose:InputStorePaymentPurpose option:PremiumGiftCodeOption = InputInvoice;
inputInvoiceStars#65f00ce3 purpose:InputStorePaymentPurpose = InputInvoice;
inputInvoiceChatInviteSubscription#34e793f1 hash:string = InputInvoice;
inputInvoiceStarGift#e8625e92 flags:# hide_name:flags.0?true include_upgrade:flags.2?true peer:InputPeer gift_id:long message:flags.1?TextWithEntities = InputInvoice;
inputInvoiceStarGiftUpgrade#4d818d5d flags:# keep_original_details:flags.0?true stargift:InputSavedStarGift = InputInvoice;
inputInvoiceStarGiftTransfer#4a5f5bd9 stargift:InputSavedStarGift to_id:InputPeer = InputInvoice;
inputInvoicePremiumGiftStars#dabab2ef flags:# user_id:InputUser months:int message:flags.0?TextWithEntities = InputInvoice;
inputInvoiceBusinessBotTransferStars#f4997e42 bot:InputUser stars:long = InputInvoice;
inputInvoiceStarGiftResale#c39f5324 flags:# ton:flags.0?true slug:string to_id:InputPeer = InputInvoice;
inputInvoiceStarGiftPrepaidUpgrade#9a0b48b8 peer:InputPeer hash:string = InputInvoice;

payments.exportedInvoice#aed0cbd9 url:string = payments.ExportedInvoice;

messages.transcribedAudio#cfb9d957 flags:# pending:flags.0?true transcription_id:long text:string trial_remains_num:flags.1?int trial_remains_until_date:flags.1?int = messages.TranscribedAudio;

help.premiumPromo#5334759c status_text:string status_entities:Vector<MessageEntity> video_sections:Vector<string> videos:Vector<Document> period_options:Vector<PremiumSubscriptionOption> users:Vector<User> = help.PremiumPromo;

inputStorePaymentPremiumSubscription#a6751e66 flags:# restore:flags.0?true upgrade:flags.1?true = InputStorePaymentPurpose;
inputStorePaymentGiftPremium#616f7fe8 user_id:InputUser currency:string amount:long = InputStorePaymentPurpose;
inputStorePaymentPremiumGiftCode#fb790393 flags:# users:Vector<InputUser> boost_peer:flags.0?InputPeer currency:string amount:long message:flags.1?TextWithEntities = InputStorePaymentPurpose;
inputStorePaymentPremiumGiveaway#160544ca flags:# only_new_subscribers:flags.0?true winners_are_visible:flags.3?true boost_peer:InputPeer additional_peers:flags.1?Vector<InputPeer> countries_iso2:flags.2?Vector<string> prize_description:flags.4?string random_id:long until_date:int currency:string amount:long = InputStorePaymentPurpose;
inputStorePaymentStarsTopup#f9a2a6cb flags:# stars:long currency:string amount:long spend_purpose_peer:flags.0?InputPeer = InputStorePaymentPurpose;
inputStorePaymentStarsGift#1d741ef7 user_id:InputUser stars:long currency:string amount:long = InputStorePaymentPurpose;
inputStorePaymentStarsGiveaway#751f08fa flags:# only_new_subscribers:flags.0?true winners_are_visible:flags.3?true stars:long boost_peer:InputPeer additional_peers:flags.1?Vector<InputPeer> countries_iso2:flags.2?Vector<string> prize_description:flags.4?string random_id:long until_date:int currency:string amount:long users:int = InputStorePaymentPurpose;
inputStorePaymentAuthCode#9bb2636d flags:# restore:flags.0?true phone_number:string phone_code_hash:string currency:string amount:long = InputStorePaymentPurpose;

paymentFormMethod#88f8f21b url:string title:string = PaymentFormMethod;

emojiStatusEmpty#2de11aae = EmojiStatus;
emojiStatus#e7ff068a flags:# document_id:long until:flags.0?int = EmojiStatus;
emojiStatusCollectible#7184603b flags:# collectible_id:long document_id:long title:string slug:string pattern_document_id:long center_color:int edge_color:int pattern_color:int text_color:int until:flags.0?int = EmojiStatus;
inputEmojiStatusCollectible#7141dbf flags:# collectible_id:long until:flags.0?int = EmojiStatus;

account.emojiStatusesNotModified#d08ce645 = account.EmojiStatuses;
account.emojiStatuses#90c467d1 hash:long statuses:Vector<EmojiStatus> = account.EmojiStatuses;

reactionEmpty#79f5d419 = Reaction;
reactionEmoji#1b2286b8 emoticon:string = Reaction;
reactionCustomEmoji#8935fc73 document_id:long = Reaction;
reactionPaid#523da4eb = Reaction;

chatReactionsNone#eafc32bc = ChatReactions;
chatReactionsAll#52928bca flags:# allow_custom:flags.0?true = ChatReactions;
chatReactionsSome#661d4037 reactions:Vector<Reaction> = ChatReactions;

messages.reactionsNotModified#b06fdbdf = messages.Reactions;
messages.reactions#eafdf716 hash:long reactions:Vector<Reaction> = messages.Reactions;

emailVerifyPurposeLoginSetup#4345be73 phone_number:string phone_code_hash:string = EmailVerifyPurpose;
emailVerifyPurposeLoginChange#527d22eb = EmailVerifyPurpose;
emailVerifyPurposePassport#bbf51685 = EmailVerifyPurpose;

emailVerificationCode#922e55a9 code:string = EmailVerification;
emailVerificationGoogle#db909ec2 token:string = EmailVerification;
emailVerificationApple#96d074fd token:string = EmailVerification;

account.emailVerified#2b96cd1b email:string = account.EmailVerified;
account.emailVerifiedLogin#e1bb0d61 email:string sent_code:auth.SentCode = account.EmailVerified;

premiumSubscriptionOption#5f2d1df2 flags:# current:flags.1?true can_purchase_upgrade:flags.2?true transaction:flags.3?string months:int currency:string amount:long bot_url:string store_product:flags.0?string = PremiumSubscriptionOption;

sendAsPeer#b81c7034 flags:# premium_required:flags.0?true peer:Peer = SendAsPeer;

messageExtendedMediaPreview#ad628cc8 flags:# w:flags.0?int h:flags.0?int thumb:flags.1?PhotoSize video_duration:flags.2?int = MessageExtendedMedia;
messageExtendedMedia#ee479c64 media:MessageMedia = MessageExtendedMedia;

stickerKeyword#fcfeb29c document_id:long keyword:Vector<string> = StickerKeyword;

username#b4073647 flags:# editable:flags.0?true active:flags.1?true username:string = Username;

forumTopicDeleted#23f109b id:int = ForumTopic;
forumTopic#71701da9 flags:# my:flags.1?true closed:flags.2?true pinned:flags.3?true short:flags.5?true hidden:flags.6?true id:int date:int title:string icon_color:int icon_emoji_id:flags.0?long top_message:int read_inbox_max_id:int read_outbox_max_id:int unread_count:int unread_mentions_count:int unread_reactions_count:int from_id:Peer notify_settings:PeerNotifySettings draft:flags.4?DraftMessage = ForumTopic;

messages.forumTopics#367617d3 flags:# order_by_create_date:flags.0?true count:int topics:Vector<ForumTopic> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> pts:int = messages.ForumTopics;

defaultHistoryTTL#43b46b20 period:int = DefaultHistoryTTL;

exportedContactToken#41bf109b url:string expires:int = ExportedContactToken;

requestPeerTypeUser#5f3b8a00 flags:# bot:flags.0?Bool premium:flags.1?Bool = RequestPeerType;
requestPeerTypeChat#c9f06e1b flags:# creator:flags.0?true bot_participant:flags.5?true has_username:flags.3?Bool forum:flags.4?Bool user_admin_rights:flags.1?ChatAdminRights bot_admin_rights:flags.2?ChatAdminRights = RequestPeerType;
requestPeerTypeBroadcast#339bef6c flags:# creator:flags.0?true has_username:flags.3?Bool user_admin_rights:flags.1?ChatAdminRights bot_admin_rights:flags.2?ChatAdminRights = RequestPeerType;

emojiListNotModified#481eadfa = EmojiList;
emojiList#7a1e11d1 hash:long document_id:Vector<long> = EmojiList;

emojiGroup#7a9abda9 title:string icon_emoji_id:long emoticons:Vector<string> = EmojiGroup;
emojiGroupGreeting#80d26cc7 title:string icon_emoji_id:long emoticons:Vector<string> = EmojiGroup;
emojiGroupPremium#93bcf34 title:string icon_emoji_id:long = EmojiGroup;

messages.emojiGroupsNotModified#6fb4ad87 = messages.EmojiGroups;
messages.emojiGroups#881fb94b hash:int groups:Vector<EmojiGroup> = messages.EmojiGroups;

textWithEntities#751f3146 text:string entities:Vector<MessageEntity> = TextWithEntities;

messages.translateResult#33db32f8 result:Vector<TextWithEntities> = messages.TranslatedText;

autoSaveSettings#c84834ce flags:# photos:flags.0?true videos:flags.1?true video_max_size:flags.2?long = AutoSaveSettings;

autoSaveException#81602d47 peer:Peer settings:AutoSaveSettings = AutoSaveException;

account.autoSaveSettings#4c3e069d users_settings:AutoSaveSettings chats_settings:AutoSaveSettings broadcasts_settings:AutoSaveSettings exceptions:Vector<AutoSaveException> chats:Vector<Chat> users:Vector<User> = account.AutoSaveSettings;

help.appConfigNotModified#7cde641d = help.AppConfig;
help.appConfig#dd18782e hash:int config:JSONValue = help.AppConfig;

inputBotAppID#a920bd7a id:long access_hash:long = InputBotApp;
inputBotAppShortName#908c0407 bot_id:InputUser short_name:string = InputBotApp;

botAppNotModified#5da674b7 = BotApp;
botApp#95fcd1d6 flags:# id:long access_hash:long short_name:string title:string description:string photo:Photo document:flags.0?Document hash:long = BotApp;

messages.botApp#eb50adf5 flags:# inactive:flags.0?true request_write_access:flags.1?true has_settings:flags.2?true app:BotApp = messages.BotApp;

inlineBotWebView#b57295d5 text:string url:string = InlineBotWebView;

readParticipantDate#4a4ff172 user_id:long date:int = ReadParticipantDate;

inputChatlistDialogFilter#f3e0da33 filter_id:int = InputChatlist;

exportedChatlistInvite#c5181ac flags:# title:string url:string peers:Vector<Peer> = ExportedChatlistInvite;

chatlists.exportedChatlistInvite#10e6e3a6 filter:DialogFilter invite:ExportedChatlistInvite = chatlists.ExportedChatlistInvite;

chatlists.exportedInvites#10ab6dc7 invites:Vector<ExportedChatlistInvite> chats:Vector<Chat> users:Vector<User> = chatlists.ExportedInvites;

chatlists.chatlistInviteAlready#fa87f659 filter_id:int missing_peers:Vector<Peer> already_peers:Vector<Peer> chats:Vector<Chat> users:Vector<User> = chatlists.ChatlistInvite;
chatlists.chatlistInvite#f10ece2f flags:# title_noanimate:flags.1?true title:TextWithEntities emoticon:flags.0?string peers:Vector<Peer> chats:Vector<Chat> users:Vector<User> = chatlists.ChatlistInvite;

chatlists.chatlistUpdates#93bd878d missing_peers:Vector<Peer> chats:Vector<Chat> users:Vector<User> = chatlists.ChatlistUpdates;

bots.botInfo#e8a775b0 name:string about:string description:string = bots.BotInfo;

messagePeerVote#b6cc2d5c peer:Peer option:bytes date:int = MessagePeerVote;
messagePeerVoteInputOption#74cda504 peer:Peer date:int = MessagePeerVote;
messagePeerVoteMultiple#4628f6e6 peer:Peer options:Vector<bytes> date:int = MessagePeerVote;

storyViews#8d595cd6 flags:# has_viewers:flags.1?true views_count:int forwards_count:flags.2?int reactions:flags.3?Vector<ReactionCount> reactions_count:flags.4?int recent_viewers:flags.0?Vector<long> = StoryViews;

storyItemDeleted#51e6ee4f id:int = StoryItem;
storyItemSkipped#ffadc913 flags:# close_friends:flags.8?true id:int date:int expire_date:int = StoryItem;
storyItem#edf164f1 flags:# pinned:flags.5?true public:flags.7?true close_friends:flags.8?true min:flags.9?true noforwards:flags.10?true edited:flags.11?true contacts:flags.12?true selected_contacts:flags.13?true out:flags.16?true id:int date:int from_id:flags.18?Peer fwd_from:flags.17?StoryFwdHeader expire_date:int caption:flags.0?string entities:flags.1?Vector<MessageEntity> media:MessageMedia media_areas:flags.14?Vector<MediaArea> privacy:flags.2?Vector<PrivacyRule> views:flags.3?StoryViews sent_reaction:flags.15?Reaction albums:flags.19?Vector<int> = StoryItem;

stories.allStoriesNotModified#1158fe3e flags:# state:string stealth_mode:StoriesStealthMode = stories.AllStories;
stories.allStories#6efc5e81 flags:# has_more:flags.0?true count:int state:string peer_stories:Vector<PeerStories> chats:Vector<Chat> users:Vector<User> stealth_mode:StoriesStealthMode = stories.AllStories;

stories.stories#63c3dd0a flags:# count:int stories:Vector<StoryItem> pinned_to_top:flags.0?Vector<int> chats:Vector<Chat> users:Vector<User> = stories.Stories;

storyView#b0bdeac5 flags:# blocked:flags.0?true blocked_my_stories_from:flags.1?true user_id:long date:int reaction:flags.2?Reaction = StoryView;
storyViewPublicForward#9083670b flags:# blocked:flags.0?true blocked_my_stories_from:flags.1?true message:Message = StoryView;
storyViewPublicRepost#bd74cf49 flags:# blocked:flags.0?true blocked_my_stories_from:flags.1?true peer_id:Peer story:StoryItem = StoryView;

stories.storyViewsList#59d78fc5 flags:# count:int views_count:int forwards_count:int reactions_count:int views:Vector<StoryView> chats:Vector<Chat> users:Vector<User> next_offset:flags.0?string = stories.StoryViewsList;

stories.storyViews#de9eed1d views:Vector<StoryViews> users:Vector<User> = stories.StoryViews;

inputReplyToMessage#869fbe10 flags:# reply_to_msg_id:int top_msg_id:flags.0?int reply_to_peer_id:flags.1?InputPeer quote_text:flags.2?string quote_entities:flags.3?Vector<MessageEntity> quote_offset:flags.4?int monoforum_peer_id:flags.5?InputPeer todo_item_id:flags.6?int = InputReplyTo;
inputReplyToStory#5881323a peer:InputPeer story_id:int = InputReplyTo;
inputReplyToMonoForum#69d66c45 monoforum_peer_id:InputPeer = InputReplyTo;

exportedStoryLink#3fc9053b link:string = ExportedStoryLink;

storiesStealthMode#712e27fd flags:# active_until_date:flags.0?int cooldown_until_date:flags.1?int = StoriesStealthMode;

mediaAreaCoordinates#cfc9e002 flags:# x:double y:double w:double h:double rotation:double radius:flags.0?double = MediaAreaCoordinates;

mediaAreaVenue#be82db9c coordinates:MediaAreaCoordinates geo:GeoPoint title:string address:string provider:string venue_id:string venue_type:string = MediaArea;
inputMediaAreaVenue#b282217f coordinates:MediaAreaCoordinates query_id:long result_id:string = MediaArea;
mediaAreaGeoPoint#cad5452d flags:# coordinates:MediaAreaCoordinates geo:GeoPoint address:flags.0?GeoPointAddress = MediaArea;
mediaAreaSuggestedReaction#14455871 flags:# dark:flags.0?true flipped:flags.1?true coordinates:MediaAreaCoordinates reaction:Reaction = MediaArea;
mediaAreaChannelPost#770416af coordinates:MediaAreaCoordinates channel_id:long msg_id:int = MediaArea;
inputMediaAreaChannelPost#2271f2bf coordinates:MediaAreaCoordinates channel:InputChannel msg_id:int = MediaArea;
mediaAreaUrl#37381085 coordinates:MediaAreaCoordinates url:string = MediaArea;
mediaAreaWeather#49a6549c coordinates:MediaAreaCoordinates emoji:string temperature_c:double color:int = MediaArea;
mediaAreaStarGift#5787686d coordinates:MediaAreaCoordinates slug:string = MediaArea;

peerStories#9a35e999 flags:# peer:Peer max_read_id:flags.0?int stories:Vector<StoryItem> = PeerStories;

stories.peerStories#cae68768 stories:PeerStories chats:Vector<Chat> users:Vector<User> = stories.PeerStories;

messages.webPage#fd5e12bd webpage:WebPage chats:Vector<Chat> users:Vector<User> = messages.WebPage;

premiumGiftCodeOption#257e962b flags:# users:int months:int store_product:flags.0?string store_quantity:flags.1?int currency:string amount:long = PremiumGiftCodeOption;

payments.checkedGiftCode#284a1096 flags:# via_giveaway:flags.2?true from_id:flags.4?Peer giveaway_msg_id:flags.3?int to_id:flags.0?long date:int months:int used_date:flags.1?int chats:Vector<Chat> users:Vector<User> = payments.CheckedGiftCode;

payments.giveawayInfo#4367daa0 flags:# participating:flags.0?true preparing_results:flags.3?true start_date:int joined_too_early_date:flags.1?int admin_disallowed_chat_id:flags.2?long disallowed_country:flags.4?string = payments.GiveawayInfo;
payments.giveawayInfoResults#e175e66f flags:# winner:flags.0?true refunded:flags.1?true start_date:int gift_code_slug:flags.3?string stars_prize:flags.4?long finish_date:int winners_count:int activated_count:flags.2?int = payments.GiveawayInfo;

prepaidGiveaway#b2539d54 id:long months:int quantity:int date:int = PrepaidGiveaway;
prepaidStarsGiveaway#9a9d77e0 id:long stars:long quantity:int boosts:int date:int = PrepaidGiveaway;

boost#4b3e14d6 flags:# gift:flags.1?true giveaway:flags.2?true unclaimed:flags.3?true id:string user_id:flags.0?long giveaway_msg_id:flags.2?int date:int expires:int used_gift_slug:flags.4?string multiplier:flags.5?int stars:flags.6?long = Boost;

premium.boostsList#86f8613c flags:# count:int boosts:Vector<Boost> next_offset:flags.0?string users:Vector<User> = premium.BoostsList;

myBoost#c448415c flags:# slot:int peer:flags.0?Peer date:int expires:int cooldown_until_date:flags.1?int = MyBoost;

premium.myBoosts#9ae228e2 my_boosts:Vector<MyBoost> chats:Vector<Chat> users:Vector<User> = premium.MyBoosts;

premium.boostsStatus#4959427a flags:# my_boost:flags.2?true level:int current_level_boosts:int boosts:int gift_boosts:flags.4?int next_level_boosts:flags.0?int premium_audience:flags.1?StatsPercentValue boost_url:string prepaid_giveaways:flags.3?Vector<PrepaidGiveaway> my_boost_slots:flags.2?Vector<int> = premium.BoostsStatus;

storyFwdHeader#b826e150 flags:# modified:flags.3?true from:flags.0?Peer from_name:flags.1?string story_id:flags.2?int = StoryFwdHeader;

postInteractionCountersMessage#e7058e7f msg_id:int views:int forwards:int reactions:int = PostInteractionCounters;
postInteractionCountersStory#8a480e27 story_id:int views:int forwards:int reactions:int = PostInteractionCounters;

stats.storyStats#50cd067c views_graph:StatsGraph reactions_by_emotion_graph:StatsGraph = stats.StoryStats;

publicForwardMessage#1f2bf4a message:Message = PublicForward;
publicForwardStory#edf3add0 peer:Peer story:StoryItem = PublicForward;

stats.publicForwards#93037e20 flags:# count:int forwards:Vector<PublicForward> next_offset:flags.0?string chats:Vector<Chat> users:Vector<User> = stats.PublicForwards;

peerColor#b54b5acf flags:# color:flags.0?int background_emoji_id:flags.1?long = PeerColor;

help.peerColorSet#26219a58 colors:Vector<int> = help.PeerColorSet;
help.peerColorProfileSet#767d61eb palette_colors:Vector<int> bg_colors:Vector<int> story_colors:Vector<int> = help.PeerColorSet;

help.peerColorOption#adec6ebe flags:# hidden:flags.0?true color_id:int colors:flags.1?help.PeerColorSet dark_colors:flags.2?help.PeerColorSet channel_min_level:flags.3?int group_min_level:flags.4?int = help.PeerColorOption;

help.peerColorsNotModified#2ba1f5ce = help.PeerColors;
help.peerColors#f8ed08 hash:int colors:Vector<help.PeerColorOption> = help.PeerColors;

storyReaction#6090d6d5 peer_id:Peer date:int reaction:Reaction = StoryReaction;
storyReactionPublicForward#bbab2643 message:Message = StoryReaction;
storyReactionPublicRepost#cfcd0f13 peer_id:Peer story:StoryItem = StoryReaction;

stories.storyReactionsList#aa5f789c flags:# count:int reactions:Vector<StoryReaction> chats:Vector<Chat> users:Vector<User> next_offset:flags.0?string = stories.StoryReactionsList;

savedDialog#bd87cb6c flags:# pinned:flags.2?true peer:Peer top_message:int = SavedDialog;
monoForumDialog#64407ea7 flags:# unread_mark:flags.3?true nopaid_messages_exception:flags.4?true peer:Peer top_message:int read_inbox_max_id:int read_outbox_max_id:int unread_count:int unread_reactions_count:int draft:flags.1?DraftMessage = SavedDialog;

messages.savedDialogs#f83ae221 dialogs:Vector<SavedDialog> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.SavedDialogs;
messages.savedDialogsSlice#44ba9dd9 count:int dialogs:Vector<SavedDialog> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.SavedDialogs;
messages.savedDialogsNotModified#c01f6fe8 count:int = messages.SavedDialogs;

savedReactionTag#cb6ff828 flags:# reaction:Reaction title:flags.0?string count:int = SavedReactionTag;

messages.savedReactionTagsNotModified#889b59ef = messages.SavedReactionTags;
messages.savedReactionTags#3259950a tags:Vector<SavedReactionTag> hash:long = messages.SavedReactionTags;

outboxReadDate#3bb842ac date:int = OutboxReadDate;

smsjobs.eligibleToJoin#dc8b44cf terms_url:string monthly_sent_sms:int = smsjobs.EligibilityToJoin;

smsjobs.status#2aee9191 flags:# allow_international:flags.0?true recent_sent:int recent_since:int recent_remains:int total_sent:int total_since:int last_gift_slug:flags.1?string terms_url:string = smsjobs.Status;

smsJob#e6a1eeb8 job_id:string phone_number:string text:string = SmsJob;

businessWeeklyOpen#120b1ab9 start_minute:int end_minute:int = BusinessWeeklyOpen;

businessWorkHours#8c92b098 flags:# open_now:flags.0?true timezone_id:string weekly_open:Vector<BusinessWeeklyOpen> = BusinessWorkHours;

businessLocation#ac5c1af7 flags:# geo_point:flags.0?GeoPoint address:string = BusinessLocation;

inputBusinessRecipients#6f8b32aa flags:# existing_chats:flags.0?true new_chats:flags.1?true contacts:flags.2?true non_contacts:flags.3?true exclude_selected:flags.5?true users:flags.4?Vector<InputUser> = InputBusinessRecipients;

businessRecipients#21108ff7 flags:# existing_chats:flags.0?true new_chats:flags.1?true contacts:flags.2?true non_contacts:flags.3?true exclude_selected:flags.5?true users:flags.4?Vector<long> = BusinessRecipients;

businessAwayMessageScheduleAlways#c9b9e2b9 = BusinessAwayMessageSchedule;
businessAwayMessageScheduleOutsideWorkHours#c3f2f501 = BusinessAwayMessageSchedule;
businessAwayMessageScheduleCustom#cc4d9ecc start_date:int end_date:int = BusinessAwayMessageSchedule;

inputBusinessGreetingMessage#194cb3b shortcut_id:int recipients:InputBusinessRecipients no_activity_days:int = InputBusinessGreetingMessage;

businessGreetingMessage#e519abab shortcut_id:int recipients:BusinessRecipients no_activity_days:int = BusinessGreetingMessage;

inputBusinessAwayMessage#832175e0 flags:# offline_only:flags.0?true shortcut_id:int schedule:BusinessAwayMessageSchedule recipients:InputBusinessRecipients = InputBusinessAwayMessage;

businessAwayMessage#ef156a5c flags:# offline_only:flags.0?true shortcut_id:int schedule:BusinessAwayMessageSchedule recipients:BusinessRecipients = BusinessAwayMessage;

timezone#ff9289f5 id:string name:string utc_offset:int = Timezone;

help.timezonesListNotModified#970708cc = help.TimezonesList;
help.timezonesList#7b74ed71 timezones:Vector<Timezone> hash:int = help.TimezonesList;

quickReply#697102b shortcut_id:int shortcut:string top_message:int count:int = QuickReply;

inputQuickReplyShortcut#24596d41 shortcut:string = InputQuickReplyShortcut;
inputQuickReplyShortcutId#1190cf1 shortcut_id:int = InputQuickReplyShortcut;

messages.quickReplies#c68d6695 quick_replies:Vector<QuickReply> messages:Vector<Message> chats:Vector<Chat> users:Vector<User> = messages.QuickReplies;
messages.quickRepliesNotModified#5f91eb5b = messages.QuickReplies;

connectedBot#cd64636c flags:# bot_id:long recipients:BusinessBotRecipients rights:BusinessBotRights = ConnectedBot;

account.connectedBots#17d7f87b connected_bots:Vector<ConnectedBot> users:Vector<User> = account.ConnectedBots;

messages.dialogFilters#2ad93719 flags:# tags_enabled:flags.0?true filters:Vector<DialogFilter> = messages.DialogFilters;

birthday#6c8e1e06 flags:# day:int month:int year:flags.0?int = Birthday;

botBusinessConnection#8f34b2f5 flags:# disabled:flags.1?true connection_id:string user_id:long dc_id:int date:int rights:flags.2?BusinessBotRights = BotBusinessConnection;

inputBusinessIntro#9c469cd flags:# title:string description:string sticker:flags.0?InputDocument = InputBusinessIntro;

businessIntro#5a0a066d flags:# title:string description:string sticker:flags.0?Document = BusinessIntro;

messages.myStickers#faff629d count:int sets:Vector<StickerSetCovered> = messages.MyStickers;

inputCollectibleUsername#e39460a9 username:string = InputCollectible;
inputCollectiblePhone#a2e214a4 phone:string = InputCollectible;

fragment.collectibleInfo#6ebdff91 purchase_date:int currency:string amount:long crypto_currency:string crypto_amount:long url:string = fragment.CollectibleInfo;

inputBusinessBotRecipients#c4e5921e flags:# existing_chats:flags.0?true new_chats:flags.1?true contacts:flags.2?true non_contacts:flags.3?true exclude_selected:flags.5?true users:flags.4?Vector<InputUser> exclude_users:flags.6?Vector<InputUser> = InputBusinessBotRecipients;

businessBotRecipients#b88cf373 flags:# existing_chats:flags.0?true new_chats:flags.1?true contacts:flags.2?true non_contacts:flags.3?true exclude_selected:flags.5?true users:flags.4?Vector<long> exclude_users:flags.6?Vector<long> = BusinessBotRecipients;

contactBirthday#1d998733 contact_id:long birthday:Birthday = ContactBirthday;

contacts.contactBirthdays#114ff30d contacts:Vector<ContactBirthday> users:Vector<User> = contacts.ContactBirthdays;

missingInvitee#628c9224 flags:# premium_would_allow_invite:flags.0?true premium_required_for_pm:flags.1?true user_id:long = MissingInvitee;

messages.invitedUsers#7f5defa6 updates:Updates missing_invitees:Vector<MissingInvitee> = messages.InvitedUsers;

inputBusinessChatLink#11679fa7 flags:# message:string entities:flags.0?Vector<MessageEntity> title:flags.1?string = InputBusinessChatLink;

businessChatLink#b4ae666f flags:# link:string message:string entities:flags.0?Vector<MessageEntity> title:flags.1?string views:int = BusinessChatLink;

account.businessChatLinks#ec43a2d1 links:Vector<BusinessChatLink> chats:Vector<Chat> users:Vector<User> = account.BusinessChatLinks;

account.resolvedBusinessChatLinks#9a23af21 flags:# peer:Peer message:string entities:flags.0?Vector<MessageEntity> chats:Vector<Chat> users:Vector<User> = account.ResolvedBusinessChatLinks;

requestedPeerUser#d62ff46a flags:# user_id:long first_name:flags.0?string last_name:flags.0?string username:flags.1?string photo:flags.2?Photo = RequestedPeer;
requestedPeerChat#7307544f flags:# chat_id:long title:flags.0?string photo:flags.2?Photo = RequestedPeer;
requestedPeerChannel#8ba403e4 flags:# channel_id:long title:flags.0?string username:flags.1?string photo:flags.2?Photo = RequestedPeer;

sponsoredMessageReportOption#430d3150 text:string option:bytes = SponsoredMessageReportOption;

channels.sponsoredMessageReportResultChooseOption#846f9e42 title:string options:Vector<SponsoredMessageReportOption> = channels.SponsoredMessageReportResult;
channels.sponsoredMessageReportResultAdsHidden#3e3bcf2f = channels.SponsoredMessageReportResult;
channels.sponsoredMessageReportResultReported#ad798849 = channels.SponsoredMessageReportResult;

reactionNotificationsFromContacts#bac3a61a = ReactionNotificationsFrom;
reactionNotificationsFromAll#4b9e22a0 = ReactionNotificationsFrom;

reactionsNotifySettings#56e34970 flags:# messages_notify_from:flags.0?ReactionNotificationsFrom stories_notify_from:flags.1?ReactionNotificationsFrom sound:NotificationSound show_previews:Bool = ReactionsNotifySettings;

availableEffect#93c3e27e flags:# premium_required:flags.2?true id:long emoticon:string static_icon_id:flags.0?long effect_sticker_id:long effect_animation_id:flags.1?long = AvailableEffect;

messages.availableEffectsNotModified#d1ed9a5b = messages.AvailableEffects;
messages.availableEffects#bddb616e hash:int effects:Vector<AvailableEffect> documents:Vector<Document> = messages.AvailableEffects;

factCheck#b89bfccf flags:# need_check:flags.0?true country:flags.1?string text:flags.1?TextWithEntities hash:long = FactCheck;

starsTransactionPeerUnsupported#95f2bfe4 = StarsTransactionPeer;
starsTransactionPeerAppStore#b457b375 = StarsTransactionPeer;
starsTransactionPeerPlayMarket#7b560a0b = StarsTransactionPeer;
starsTransactionPeerPremiumBot#250dbaf8 = StarsTransactionPeer;
starsTransactionPeerFragment#e92fd902 = StarsTransactionPeer;
starsTransactionPeer#d80da15d peer:Peer = StarsTransactionPeer;
starsTransactionPeerAds#60682812 = StarsTransactionPeer;
starsTransactionPeerAPI#f9677aad = StarsTransactionPeer;

starsTopupOption#bd915c0 flags:# extended:flags.1?true stars:long store_product:flags.0?string currency:string amount:long = StarsTopupOption;

starsTransaction#13659eb0 flags:# refund:flags.3?true pending:flags.4?true failed:flags.6?true gift:flags.10?true reaction:flags.11?true stargift_upgrade:flags.18?true business_transfer:flags.21?true stargift_resale:flags.22?true posts_search:flags.24?true stargift_prepaid_upgrade:flags.25?true id:string amount:StarsAmount date:int peer:StarsTransactionPeer title:flags.0?string description:flags.1?string photo:flags.2?WebDocument transaction_date:flags.5?int transaction_url:flags.5?string bot_payload:flags.7?bytes msg_id:flags.8?int extended_media:flags.9?Vector<MessageMedia> subscription_period:flags.12?int giveaway_post_id:flags.13?int stargift:flags.14?StarGift floodskip_number:flags.15?int starref_commission_permille:flags.16?int starref_peer:flags.17?Peer starref_amount:flags.17?StarsAmount paid_messages:flags.19?int premium_gift_months:flags.20?int ads_proceeds_from_date:flags.23?int ads_proceeds_to_date:flags.23?int = StarsTransaction;

payments.starsStatus#6c9ce8ed flags:# balance:StarsAmount subscriptions:flags.1?Vector<StarsSubscription> subscriptions_next_offset:flags.2?string subscriptions_missing_balance:flags.4?long history:flags.3?Vector<StarsTransaction> next_offset:flags.0?string chats:Vector<Chat> users:Vector<User> = payments.StarsStatus;

foundStory#e87acbc0 peer:Peer story:StoryItem = FoundStory;

stories.foundStories#e2de7737 flags:# count:int stories:Vector<FoundStory> next_offset:flags.0?string chats:Vector<Chat> users:Vector<User> = stories.FoundStories;

geoPointAddress#de4c5d93 flags:# country_iso2:string state:flags.0?string city:flags.1?string street:flags.2?string = GeoPointAddress;

starsRevenueStatus#febe5491 flags:# withdrawal_enabled:flags.0?true current_balance:StarsAmount available_balance:StarsAmount overall_revenue:StarsAmount next_withdrawal_at:flags.1?int = StarsRevenueStatus;

payments.starsRevenueStats#6c207376 flags:# top_hours_graph:flags.0?StatsGraph revenue_graph:StatsGraph status:StarsRevenueStatus usd_rate:double = payments.StarsRevenueStats;

payments.starsRevenueWithdrawalUrl#1dab80b7 url:string = payments.StarsRevenueWithdrawalUrl;

payments.starsRevenueAdsAccountUrl#394e7f21 url:string = payments.StarsRevenueAdsAccountUrl;

inputStarsTransaction#206ae6d1 flags:# refund:flags.0?true id:string = InputStarsTransaction;

starsGiftOption#5e0589f1 flags:# extended:flags.1?true stars:long store_product:flags.0?string currency:string amount:long = StarsGiftOption;

bots.popularAppBots#1991b13b flags:# next_offset:flags.0?string users:Vector<User> = bots.PopularAppBots;

botPreviewMedia#23e91ba3 date:int media:MessageMedia = BotPreviewMedia;

bots.previewInfo#ca71d64 media:Vector<BotPreviewMedia> lang_codes:Vector<string> = bots.PreviewInfo;

starsSubscriptionPricing#5416d58 period:int amount:long = StarsSubscriptionPricing;

starsSubscription#2e6eab1a flags:# canceled:flags.0?true can_refulfill:flags.1?true missing_balance:flags.2?true bot_canceled:flags.7?true id:string peer:Peer until_date:int pricing:StarsSubscriptionPricing chat_invite_hash:flags.3?string title:flags.4?string photo:flags.5?WebDocument invoice_slug:flags.6?string = StarsSubscription;

messageReactor#4ba3a95a flags:# top:flags.0?true my:flags.1?true anonymous:flags.2?true peer_id:flags.3?Peer count:int = MessageReactor;

starsGiveawayOption#94ce852a flags:# extended:flags.0?true default:flags.1?true stars:long yearly_boosts:int store_product:flags.2?string currency:string amount:long winners:Vector<StarsGiveawayWinnersOption> = StarsGiveawayOption;

starsGiveawayWinnersOption#54236209 flags:# default:flags.0?true users:int per_user_stars:long = StarsGiveawayWinnersOption;

starGift#80ac53c3 flags:# limited:flags.0?true sold_out:flags.1?true birthday:flags.2?true require_premium:flags.7?true limited_per_user:flags.8?true id:long sticker:Document stars:long availability_remains:flags.0?int availability_total:flags.0?int availability_resale:flags.4?long convert_stars:long first_sale_date:flags.1?int last_sale_date:flags.1?int upgrade_stars:flags.3?long resell_min_stars:flags.4?long title:flags.5?string released_by:flags.6?Peer per_user_total:flags.8?int per_user_remains:flags.8?int locked_until_date:flags.9?int = StarGift;
starGiftUnique#1befe865 flags:# require_premium:flags.6?true resale_ton_only:flags.7?true theme_available:flags.9?true id:long gift_id:long title:string slug:string num:int owner_id:flags.0?Peer owner_name:flags.1?string owner_address:flags.2?string attributes:Vector<StarGiftAttribute> availability_issued:int availability_total:int gift_address:flags.3?string resell_amount:flags.4?Vector<StarsAmount> released_by:flags.5?Peer value_amount:flags.8?long value_currency:flags.8?string theme_peer:flags.10?Peer = StarGift;

payments.starGiftsNotModified#a388a368 = payments.StarGifts;
payments.starGifts#2ed82995 hash:int gifts:Vector<StarGift> chats:Vector<Chat> users:Vector<User> = payments.StarGifts;

messageReportOption#7903e3d9 text:string option:bytes = MessageReportOption;

reportResultChooseOption#f0e4e0b6 title:string options:Vector<MessageReportOption> = ReportResult;
reportResultAddComment#6f09ac31 flags:# optional:flags.0?true option:bytes = ReportResult;
reportResultReported#8db33c4b = ReportResult;

messages.botPreparedInlineMessage#8ecf0511 id:string expire_date:int = messages.BotPreparedInlineMessage;

messages.preparedInlineMessage#ff57708d query_id:long result:BotInlineResult peer_types:Vector<InlineQueryPeerType> cache_time:int users:Vector<User> = messages.PreparedInlineMessage;

botAppSettings#c99b1950 flags:# placeholder_path:flags.0?bytes background_color:flags.1?int background_dark_color:flags.2?int header_color:flags.3?int header_dark_color:flags.4?int = BotAppSettings;

starRefProgram#dd0c66f2 flags:# bot_id:long commission_permille:int duration_months:flags.0?int end_date:flags.1?int daily_revenue_per_user:flags.2?StarsAmount = StarRefProgram;

connectedBotStarRef#19a13f71 flags:# revoked:flags.1?true url:string date:int bot_id:long commission_permille:int duration_months:flags.0?int participants:long revenue:long = ConnectedBotStarRef;

payments.connectedStarRefBots#98d5ea1d count:int connected_bots:Vector<ConnectedBotStarRef> users:Vector<User> = payments.ConnectedStarRefBots;

payments.suggestedStarRefBots#b4d5d859 flags:# count:int suggested_bots:Vector<StarRefProgram> users:Vector<User> next_offset:flags.0?string = payments.SuggestedStarRefBots;

starsAmount#bbb6b4a3 amount:long nanos:int = StarsAmount;
starsTonAmount#74aee3e0 amount:long = StarsAmount;

messages.foundStickersNotModified#6010c534 flags:# next_offset:flags.0?int = messages.FoundStickers;
messages.foundStickers#82c9e290 flags:# next_offset:flags.0?int hash:long stickers:Vector<Document> = messages.FoundStickers;

botVerifierSettings#b0cd6617 flags:# can_modify_custom_description:flags.1?true icon:long company:string custom_description:flags.0?string = BotVerifierSettings;

botVerification#f93cd45c bot_id:long icon:long description:string = BotVerification;

starGiftAttributeModel#39d99013 name:string document:Document rarity_permille:int = StarGiftAttribute;
starGiftAttributePattern#13acff19 name:string document:Document rarity_permille:int = StarGiftAttribute;
starGiftAttributeBackdrop#d93d859c name:string backdrop_id:int center_color:int edge_color:int pattern_color:int text_color:int rarity_permille:int = StarGiftAttribute;
starGiftAttributeOriginalDetails#e0bff26c flags:# sender_id:flags.0?Peer recipient_id:Peer date:int message:flags.1?TextWithEntities = StarGiftAttribute;

payments.starGiftUpgradePreview#167bd90b sample_attributes:Vector<StarGiftAttribute> = payments.StarGiftUpgradePreview;

users.users#62d706b8 users:Vector<User> = users.Users;
users.usersSlice#315a4974 count:int users:Vector<User> = users.Users;

payments.uniqueStarGift#416c56e8 gift:StarGift chats:Vector<Chat> users:Vector<User> = payments.UniqueStarGift;

messages.webPagePreview#8c9a88ac media:MessageMedia chats:Vector<Chat> users:Vector<User> = messages.WebPagePreview;

savedStarGift#19a9b572 flags:# name_hidden:flags.0?true unsaved:flags.5?true refunded:flags.9?true can_upgrade:flags.10?true pinned_to_top:flags.12?true upgrade_separate:flags.17?true from_id:flags.1?Peer date:int gift:StarGift message:flags.2?TextWithEntities msg_id:flags.3?int saved_id:flags.11?long convert_stars:flags.4?long upgrade_stars:flags.6?long can_export_at:flags.7?int transfer_stars:flags.8?long can_transfer_at:flags.13?int can_resell_at:flags.14?int collection_id:flags.15?Vector<int> prepaid_upgrade_hash:flags.16?string = SavedStarGift;

payments.savedStarGifts#95f389b1 flags:# count:int chat_notifications_enabled:flags.1?Bool gifts:Vector<SavedStarGift> next_offset:flags.0?string chats:Vector<Chat> users:Vector<User> = payments.SavedStarGifts;

inputSavedStarGiftUser#69279795 msg_id:int = InputSavedStarGift;
inputSavedStarGiftChat#f101aa7f peer:InputPeer saved_id:long = InputSavedStarGift;
inputSavedStarGiftSlug#2085c238 slug:string = InputSavedStarGift;

payments.starGiftWithdrawalUrl#84aa3a9c url:string = payments.StarGiftWithdrawalUrl;

paidReactionPrivacyDefault#206ad49e = PaidReactionPrivacy;
paidReactionPrivacyAnonymous#1f0c1ad9 = PaidReactionPrivacy;
paidReactionPrivacyPeer#dc6cfcf0 peer:InputPeer = PaidReactionPrivacy;

account.paidMessagesRevenue#1e109708 stars_amount:long = account.PaidMessagesRevenue;

requirementToContactEmpty#50a9839 = RequirementToContact;
requirementToContactPremium#e581e4e9 = RequirementToContact;
requirementToContactPaidMessages#b4f67e93 stars_amount:long = RequirementToContact;

businessBotRights#a0624cf7 flags:# reply:flags.0?true read_messages:flags.1?true delete_sent_messages:flags.2?true delete_received_messages:flags.3?true edit_name:flags.4?true edit_bio:flags.5?true edit_profile_photo:flags.6?true edit_username:flags.7?true view_gifts:flags.8?true sell_gifts:flags.9?true change_gift_settings:flags.10?true transfer_and_upgrade_gifts:flags.11?true transfer_stars:flags.12?true manage_stories:flags.13?true = BusinessBotRights;

disallowedGiftsSettings#71f276c4 flags:# disallow_unlimited_stargifts:flags.0?true disallow_limited_stargifts:flags.1?true disallow_unique_stargifts:flags.2?true disallow_premium_gifts:flags.3?true = DisallowedGiftsSettings;

sponsoredPeer#c69708d3 flags:# random_id:bytes peer:Peer sponsor_info:flags.0?string additional_info:flags.1?string = SponsoredPeer;

contacts.sponsoredPeersEmpty#ea32b4b1 = contacts.SponsoredPeers;
contacts.sponsoredPeers#eb032884 peers:Vector<SponsoredPeer> chats:Vector<Chat> users:Vector<User> = contacts.SponsoredPeers;

starGiftAttributeIdModel#48aaae3c document_id:long = StarGiftAttributeId;
starGiftAttributeIdPattern#4a162433 document_id:long = StarGiftAttributeId;
starGiftAttributeIdBackdrop#1f01c757 backdrop_id:int = StarGiftAttributeId;

starGiftAttributeCounter#2eb1b658 attribute:StarGiftAttributeId count:int = StarGiftAttributeCounter;

payments.resaleStarGifts#947a12df flags:# count:int gifts:Vector<StarGift> next_offset:flags.0?string attributes:flags.1?Vector<StarGiftAttribute> attributes_hash:flags.1?long chats:Vector<Chat> counters:flags.2?Vector<StarGiftAttributeCounter> users:Vector<User> = payments.ResaleStarGifts;

stories.canSendStoryCount#c387c04e count_remains:int = stories.CanSendStoryCount;

pendingSuggestion#e7e82e12 suggestion:string title:TextWithEntities description:TextWithEntities url:string = PendingSuggestion;

todoItem#cba9a52f id:int title:TextWithEntities = TodoItem;

todoList#49b92a26 flags:# others_can_append:flags.0?true others_can_complete:flags.1?true title:TextWithEntities list:Vector<TodoItem> = TodoList;

todoCompletion#4cc120b7 id:int completed_by:long date:int = TodoCompletion;

suggestedPost#e8e37e5 flags:# accepted:flags.1?true rejected:flags.2?true price:flags.3?StarsAmount schedule_date:flags.0?int = SuggestedPost;

starsRating#1b0e4f07 flags:# level:int current_level_stars:long stars:long next_level_stars:flags.0?long = StarsRating;

starGiftCollection#9d6b13b0 flags:# collection_id:int title:string icon:flags.0?Document gifts_count:int hash:long = StarGiftCollection;

payments.starGiftCollectionsNotModified#a0ba4f17 = payments.StarGiftCollections;
payments.starGiftCollections#8a2932f3 collections:Vector<StarGiftCollection> = payments.StarGiftCollections;

storyAlbum#9325705a flags:# album_id:int title:string icon_photo:flags.0?Photo icon_video:flags.1?Document = StoryAlbum;

stories.albumsNotModified#564edaeb = stories.Albums;
stories.albums#c3987a3a hash:long albums:Vector<StoryAlbum> = stories.Albums;

searchPostsFlood#3e0b5b6a flags:# query_is_free:flags.0?true total_daily:int remains:int wait_till:flags.1?int stars_amount:long = SearchPostsFlood;

payments.uniqueStarGiftValueInfo#512fe446 flags:# last_sale_on_fragment:flags.1?true value_is_average:flags.6?true currency:string value:long initial_sale_date:int initial_sale_stars:long initial_sale_price:long last_sale_date:flags.0?int last_sale_price:flags.0?long floor_price:flags.2?long average_price:flags.3?long listed_count:flags.4?int fragment_listed_count:flags.5?int fragment_listed_url:flags.5?string = payments.UniqueStarGiftValueInfo;

profileTabPosts#b98cd696 = ProfileTab;
profileTabGifts#4d4bd46a = ProfileTab;
profileTabMedia#72c64955 = ProfileTab;
profileTabFiles#ab339c00 = ProfileTab;
profileTabMusic#9f27d26e = ProfileTab;
profileTabVoice#e477092e = ProfileTab;
profileTabLinks#d3656499 = ProfileTab;
profileTabGifs#a2c0f695 = ProfileTab;

users.savedMusicNotModified#e3878aa4 count:int = users.SavedMusic;
users.savedMusic#34a2f297 count:int documents:Vector<Document> = users.SavedMusic;

account.savedMusicIdsNotModified#4fc81d6e = account.SavedMusicIds;
account.savedMusicIds#998d6636 ids:Vector<long> = account.SavedMusicIds;

payments.checkCanSendGiftResultOk#374fa7ad = payments.CheckCanSendGiftResult;
payments.checkCanSendGiftResultFail#d5e58274 reason:TextWithEntities = payments.CheckCanSendGiftResult;

inputChatThemeEmpty#83268483 = InputChatTheme;
inputChatTheme#c93de95c emoticon:string = InputChatTheme;
inputChatThemeUniqueGift#87e5dfe4 slug:string = InputChatTheme;

---functions---

invokeAfterMsg#cb9f372d {X:Type} msg_id:long query:!X = X;
invokeAfterMsgs#3dc4b4f0 {X:Type} msg_ids:Vector<long> query:!X = X;
initConnection#c1cd5ea9 {X:Type} flags:# api_id:int device_model:string system_version:string app_version:string system_lang_code:string lang_pack:string lang_code:string proxy:flags.0?InputClientProxy params:flags.1?JSONValue query:!X = X;
invokeWithLayer#da9b0d0d {X:Type} layer:int query:!X = X;
invokeWithoutUpdates#bf9459b7 {X:Type} query:!X = X;
invokeWithMessagesRange#365275f2 {X:Type} range:MessageRange query:!X = X;
invokeWithTakeout#aca9fd2e {X:Type} takeout_id:long query:!X = X;
invokeWithBusinessConnection#dd289f8e {X:Type} connection_id:string query:!X = X;
invokeWithGooglePlayIntegrity#1df92984 {X:Type} nonce:string token:string query:!X = X;
invokeWithApnsSecret#0dae54f8 {X:Type} nonce:string secret:string query:!X = X;
invokeWithReCaptcha#adbb0f94 {X:Type} token:string query:!X = X;

auth.sendCode#a677244f phone_number:string api_id:int api_hash:string settings:CodeSettings = auth.SentCode;
auth.signUp#aac7b717 flags:# no_joined_notifications:flags.0?true phone_number:string phone_code_hash:string first_name:string last_name:string = auth.Authorization;
auth.signIn#8d52a951 flags:# phone_number:string phone_code_hash:string phone_code:flags.0?string email_verification:flags.1?EmailVerification = auth.Authorization;
auth.logOut#3e72ba19 = auth.LoggedOut;
auth.resetAuthorizations#9fab0d1a = Bool;
auth.exportAuthorization#e5bfffcd dc_id:int = auth.ExportedAuthorization;
auth.importAuthorization#a57a7dad id:long bytes:bytes = auth.Authorization;
auth.bindTempAuthKey#cdd42a05 perm_auth_key_id:long nonce:long expires_at:int encrypted_message:bytes = Bool;
auth.importBotAuthorization#67a3ff2c flags:int api_id:int api_hash:string bot_auth_token:string = auth.Authorization;
auth.checkPassword#d18b4d16 password:InputCheckPasswordSRP = auth.Authorization;
auth.requestPasswordRecovery#d897bc66 = auth.PasswordRecovery;
auth.recoverPassword#37096c70 flags:# code:string new_settings:flags.0?account.PasswordInputSettings = auth.Authorization;
auth.resendCode#cae47523 flags:# phone_number:string phone_code_hash:string reason:flags.0?string = auth.SentCode;
auth.cancelCode#1f040578 phone_number:string phone_code_hash:string = Bool;
auth.dropTempAuthKeys#8e48a188 except_auth_keys:Vector<long> = Bool;
auth.exportLoginToken#b7e085fe api_id:int api_hash:string except_ids:Vector<long> = auth.LoginToken;
auth.importLoginToken#95ac5ce4 token:bytes = auth.LoginToken;
auth.acceptLoginToken#e894ad4d token:bytes = Authorization;
auth.checkRecoveryPassword#d36bf79 code:string = Bool;
auth.importWebTokenAuthorization#2db873a9 api_id:int api_hash:string web_auth_token:string = auth.Authorization;
auth.requestFirebaseSms#8e39261e flags:# phone_number:string phone_code_hash:string safety_net_token:flags.0?string play_integrity_token:flags.2?string ios_push_secret:flags.1?string = Bool;
auth.resetLoginEmail#7e960193 phone_number:string phone_code_hash:string = auth.SentCode;
auth.reportMissingCode#cb9deff6 phone_number:string phone_code_hash:string mnc:string = Bool;

account.registerDevice#ec86017a flags:# no_muted:flags.0?true token_type:int token:string app_sandbox:Bool secret:bytes other_uids:Vector<long> = Bool;
account.unregisterDevice#6a0d3206 token_type:int token:string other_uids:Vector<long> = Bool;
account.updateNotifySettings#84be5b93 peer:InputNotifyPeer settings:InputPeerNotifySettings = Bool;
account.getNotifySettings#12b3ad31 peer:InputNotifyPeer = PeerNotifySettings;
account.resetNotifySettings#db7e1747 = Bool;
account.updateProfile#78515775 flags:# first_name:flags.0?string last_name:flags.1?string about:flags.2?string = User;
account.updateStatus#6628562c offline:Bool = Bool;
account.getWallPapers#7967d36 hash:long = account.WallPapers;
account.reportPeer#c5ba3d86 peer:InputPeer reason:ReportReason message:string = Bool;
account.checkUsername#2714d86c username:string = Bool;
account.updateUsername#3e0bdd7c username:string = User;
account.getPrivacy#dadbc950 key:InputPrivacyKey = account.PrivacyRules;
account.setPrivacy#c9f81ce8 key:InputPrivacyKey rules:Vector<InputPrivacyRule> = account.PrivacyRules;
account.deleteAccount#a2c0cf74 flags:# reason:string password:flags.0?InputCheckPasswordSRP = Bool;
account.getAccountTTL#8fc711d = AccountDaysTTL;
account.setAccountTTL#2442485e ttl:AccountDaysTTL = Bool;
account.sendChangePhoneCode#82574ae5 phone_number:string settings:CodeSettings = auth.SentCode;
account.changePhone#70c32edb phone_number:string phone_code_hash:string phone_code:string = User;
account.updateDeviceLocked#38df3532 period:int = Bool;
account.getAuthorizations#e320c158 = account.Authorizations;
account.resetAuthorization#df77f3bc hash:long = Bool;
account.getPassword#548a30f5 = account.Password;
account.getPasswordSettings#9cd4eaf9 password:InputCheckPasswordSRP = account.PasswordSettings;
account.updatePasswordSettings#a59b102f password:InputCheckPasswordSRP new_settings:account.PasswordInputSettings = Bool;
account.sendConfirmPhoneCode#1b3faa88 hash:string settings:CodeSettings = auth.SentCode;
account.confirmPhone#5f2178c3 phone_code_hash:string phone_code:string = Bool;
account.getTmpPassword#449e0b51 password:InputCheckPasswordSRP period:int = account.TmpPassword;
account.getWebAuthorizations#182e6d6f = account.WebAuthorizations;
account.resetWebAuthorization#2d01b9ef hash:long = Bool;
account.resetWebAuthorizations#682d2594 = Bool;
account.getAllSecureValues#b288bc7d = Vector<SecureValue>;
account.getSecureValue#73665bc2 types:Vector<SecureValueType> = Vector<SecureValue>;
account.saveSecureValue#899fe31d value:InputSecureValue secure_secret_id:long = SecureValue;
account.deleteSecureValue#b880bc4b types:Vector<SecureValueType> = Bool;
account.getAuthorizationForm#a929597a bot_id:long scope:string public_key:string = account.AuthorizationForm;
account.acceptAuthorization#f3ed4c73 bot_id:long scope:string public_key:string value_hashes:Vector<SecureValueHash> credentials:SecureCredentialsEncrypted = Bool;
account.sendVerifyPhoneCode#a5a356f9 phone_number:string settings:CodeSettings = auth.SentCode;
account.verifyPhone#4dd3a7f6 phone_number:string phone_code_hash:string phone_code:string = Bool;
account.sendVerifyEmailCode#98e037bb purpose:EmailVerifyPurpose email:string = account.SentEmailCode;
account.verifyEmail#32da4cf purpose:EmailVerifyPurpose verification:EmailVerification = account.EmailVerified;
account.initTakeoutSession#8ef3eab0 flags:# contacts:flags.0?true message_users:flags.1?true message_chats:flags.2?true message_megagroups:flags.3?true message_channels:flags.4?true files:flags.5?true file_max_size:flags.5?long = account.Takeout;
account.finishTakeoutSession#1d2652ee flags:# success:flags.0?true = Bool;
account.confirmPasswordEmail#8fdf1920 code:string = Bool;
account.resendPasswordEmail#7a7f2a15 = Bool;
account.cancelPasswordEmail#c1cbd5b6 = Bool;
account.getContactSignUpNotification#9f07c728 = Bool;
account.setContactSignUpNotification#cff43f61 silent:Bool = Bool;
account.getNotifyExceptions#53577479 flags:# compare_sound:flags.1?true compare_stories:flags.2?true peer:flags.0?InputNotifyPeer = Updates;
account.getWallPaper#fc8ddbea wallpaper:InputWallPaper = WallPaper;
account.uploadWallPaper#e39a8f03 flags:# for_chat:flags.0?true file:InputFile mime_type:string settings:WallPaperSettings = WallPaper;
account.saveWallPaper#6c5a5b37 wallpaper:InputWallPaper unsave:Bool settings:WallPaperSettings = Bool;
account.installWallPaper#feed5769 wallpaper:InputWallPaper settings:WallPaperSettings = Bool;
account.resetWallPapers#bb3b9804 = Bool;
account.getAutoDownloadSettings#56da0b3f = account.AutoDownloadSettings;
account.saveAutoDownloadSettings#76f36233 flags:# low:flags.0?true high:flags.1?true settings:AutoDownloadSettings = Bool;
account.uploadTheme#1c3db333 flags:# file:InputFile thumb:flags.0?InputFile file_name:string mime_type:string = Document;
account.createTheme#652e4400 flags:# slug:string title:string document:flags.2?InputDocument settings:flags.3?Vector<InputThemeSettings> = Theme;
account.updateTheme#2bf40ccc flags:# format:string theme:InputTheme slug:flags.0?string title:flags.1?string document:flags.2?InputDocument settings:flags.3?Vector<InputThemeSettings> = Theme;
account.saveTheme#f257106c theme:InputTheme unsave:Bool = Bool;
account.installTheme#c727bb3b flags:# dark:flags.0?true theme:flags.1?InputTheme format:flags.2?string base_theme:flags.3?BaseTheme = Bool;
account.getTheme#3a5869ec format:string theme:InputTheme = Theme;
account.getThemes#7206e458 format:string hash:long = account.Themes;
account.setContentSettings#b574b16b flags:# sensitive_enabled:flags.0?true = Bool;
account.getContentSettings#8b9b4dae = account.ContentSettings;
account.getMultiWallPapers#65ad71dc wallpapers:Vector<InputWallPaper> = Vector<WallPaper>;
account.getGlobalPrivacySettings#eb2b4cf6 = GlobalPrivacySettings;
account.setGlobalPrivacySettings#1edaaac2 settings:GlobalPrivacySettings = GlobalPrivacySettings;
account.reportProfilePhoto#fa8cc6f5 peer:InputPeer photo_id:InputPhoto reason:ReportReason message:string = Bool;
account.resetPassword#9308ce1b = account.ResetPasswordResult;
account.declinePasswordReset#4c9409f6 = Bool;
account.getChatThemes#d638de89 hash:long = account.Themes;
account.setAuthorizationTTL#bf899aa0 authorization_ttl_days:int = Bool;
account.changeAuthorizationSettings#40f48462 flags:# confirmed:flags.3?true hash:long encrypted_requests_disabled:flags.0?Bool call_requests_disabled:flags.1?Bool = Bool;
account.getSavedRingtones#e1902288 hash:long = account.SavedRingtones;
account.saveRingtone#3dea5b03 id:InputDocument unsave:Bool = account.SavedRingtone;
account.uploadRingtone#831a83a2 file:InputFile file_name:string mime_type:string = Document;
account.updateEmojiStatus#fbd3de6b emoji_status:EmojiStatus = Bool;
account.getDefaultEmojiStatuses#d6753386 hash:long = account.EmojiStatuses;
account.getRecentEmojiStatuses#f578105 hash:long = account.EmojiStatuses;
account.clearRecentEmojiStatuses#18201aae = Bool;
account.reorderUsernames#ef500eab order:Vector<string> = Bool;
account.toggleUsername#58d6b376 username:string active:Bool = Bool;
account.getDefaultProfilePhotoEmojis#e2750328 hash:long = EmojiList;
account.getDefaultGroupPhotoEmojis#915860ae hash:long = EmojiList;
account.getAutoSaveSettings#adcbbcda = account.AutoSaveSettings;
account.saveAutoSaveSettings#d69b8361 flags:# users:flags.0?true chats:flags.1?true broadcasts:flags.2?true peer:flags.3?InputPeer settings:AutoSaveSettings = Bool;
account.deleteAutoSaveExceptions#53bc0020 = Bool;
account.invalidateSignInCodes#ca8ae8ba codes:Vector<string> = Bool;
account.updateColor#7cefa15d flags:# for_profile:flags.1?true color:flags.2?int background_emoji_id:flags.0?long = Bool;
account.getDefaultBackgroundEmojis#a60ab9ce hash:long = EmojiList;
account.getChannelDefaultEmojiStatuses#7727a7d5 hash:long = account.EmojiStatuses;
account.getChannelRestrictedStatusEmojis#35a9e0d5 hash:long = EmojiList;
account.updateBusinessWorkHours#4b00e066 flags:# business_work_hours:flags.0?BusinessWorkHours = Bool;
account.updateBusinessLocation#9e6b131a flags:# geo_point:flags.1?InputGeoPoint address:flags.0?string = Bool;
account.updateBusinessGreetingMessage#66cdafc4 flags:# message:flags.0?InputBusinessGreetingMessage = Bool;
account.updateBusinessAwayMessage#a26a7fa5 flags:# message:flags.0?InputBusinessAwayMessage = Bool;
account.updateConnectedBot#66a08c7e flags:# deleted:flags.1?true rights:flags.0?BusinessBotRights bot:InputUser recipients:InputBusinessBotRecipients = Updates;
account.getConnectedBots#4ea4c80f = account.ConnectedBots;
account.getBotBusinessConnection#76a86270 connection_id:string = Updates;
account.updateBusinessIntro#a614d034 flags:# intro:flags.0?InputBusinessIntro = Bool;
account.toggleConnectedBotPaused#646e1097 peer:InputPeer paused:Bool = Bool;
account.disablePeerConnectedBot#5e437ed9 peer:InputPeer = Bool;
account.updateBirthday#cc6e0c11 flags:# birthday:flags.0?Birthday = Bool;
account.createBusinessChatLink#8851e68e link:InputBusinessChatLink = BusinessChatLink;
account.editBusinessChatLink#8c3410af slug:string link:InputBusinessChatLink = BusinessChatLink;
account.deleteBusinessChatLink#60073674 slug:string = Bool;
account.getBusinessChatLinks#6f70dde1 = account.BusinessChatLinks;
account.resolveBusinessChatLink#5492e5ee slug:string = account.ResolvedBusinessChatLinks;
account.updatePersonalChannel#d94305e0 channel:InputChannel = Bool;
account.toggleSponsoredMessages#b9d9a38d enabled:Bool = Bool;
account.getReactionsNotifySettings#6dd654c = ReactionsNotifySettings;
account.setReactionsNotifySettings#316ce548 settings:ReactionsNotifySettings = ReactionsNotifySettings;
account.getCollectibleEmojiStatuses#2e7b4543 hash:long = account.EmojiStatuses;
account.getPaidMessagesRevenue#19ba4a67 flags:# parent_peer:flags.0?InputPeer user_id:InputUser = account.PaidMessagesRevenue;
account.toggleNoPaidMessagesException#fe2eda76 flags:# refund_charged:flags.0?true require_payment:flags.2?true parent_peer:flags.1?InputPeer user_id:InputUser = Bool;
account.setMainProfileTab#5dee78b0 tab:ProfileTab = Bool;
account.saveMusic#b26732a9 flags:# unsave:flags.0?true id:InputDocument after_id:flags.1?InputDocument = Bool;
account.getSavedMusicIds#e09d5faf hash:long = account.SavedMusicIds;
account.getUniqueGiftChatThemes#fe74ef9f offset:int limit:int hash:long = account.ChatThemes;

users.getUsers#d91a548 id:Vector<InputUser> = Vector<User>;
users.getFullUser#b60f5918 id:InputUser = users.UserFull;
users.setSecureValueErrors#90c894b5 id:InputUser errors:Vector<SecureValueError> = Bool;
users.getRequirementsToContact#d89a83a3 id:Vector<InputUser> = Vector<RequirementToContact>;
users.getSavedMusic#788d7fe3 id:InputUser offset:int limit:int hash:long = users.SavedMusic;
users.getSavedMusicByID#7573a4e9 id:InputUser documents:Vector<InputDocument> = users.SavedMusic;

contacts.getContactIDs#7adc669d hash:long = Vector<int>;
contacts.getStatuses#c4a353ee = Vector<ContactStatus>;
contacts.getContacts#5dd69e12 hash:long = contacts.Contacts;
contacts.importContacts#2c800be5 contacts:Vector<InputContact> = contacts.ImportedContacts;
contacts.deleteContacts#96a0e00 id:Vector<InputUser> = Updates;
contacts.deleteByPhones#1013fd9e phones:Vector<string> = Bool;
contacts.block#2e2e8734 flags:# my_stories_from:flags.0?true id:InputPeer = Bool;
contacts.unblock#b550d328 flags:# my_stories_from:flags.0?true id:InputPeer = Bool;
contacts.getBlocked#9a868f80 flags:# my_stories_from:flags.0?true offset:int limit:int = contacts.Blocked;
contacts.search#11f812d8 q:string limit:int = contacts.Found;
contacts.resolveUsername#725afbbc flags:# username:string referer:flags.0?string = contacts.ResolvedPeer;
contacts.getTopPeers#973478b6 flags:# correspondents:flags.0?true bots_pm:flags.1?true bots_inline:flags.2?true phone_calls:flags.3?true forward_users:flags.4?true forward_chats:flags.5?true groups:flags.10?true channels:flags.15?true bots_app:flags.16?true offset:int limit:int hash:long = contacts.TopPeers;
contacts.resetTopPeerRating#1ae373ac category:TopPeerCategory peer:InputPeer = Bool;
contacts.resetSaved#879537f1 = Bool;
contacts.getSaved#82f1e39f = Vector<SavedContact>;
contacts.toggleTopPeers#8514bdda enabled:Bool = Bool;
contacts.addContact#e8f463d0 flags:# add_phone_privacy_exception:flags.0?true id:InputUser first_name:string last_name:string phone:string = Updates;
contacts.acceptContact#f831a20f id:InputUser = Updates;
contacts.getLocated#d348bc44 flags:# background:flags.1?true geo_point:InputGeoPoint self_expires:flags.0?int = Updates;
contacts.blockFromReplies#29a8962c flags:# delete_message:flags.0?true delete_history:flags.1?true report_spam:flags.2?true msg_id:int = Updates;
contacts.resolvePhone#8af94344 phone:string = contacts.ResolvedPeer;
contacts.exportContactToken#f8654027 = ExportedContactToken;
contacts.importContactToken#13005788 token:string = User;
contacts.editCloseFriends#ba6705f0 id:Vector<long> = Bool;
contacts.setBlocked#94c65c76 flags:# my_stories_from:flags.0?true id:Vector<InputPeer> limit:int = Bool;
contacts.getBirthdays#daeda864 = contacts.ContactBirthdays;
contacts.getSponsoredPeers#b6c8c393 q:string = contacts.SponsoredPeers;

messages.getMessages#63c66506 id:Vector<InputMessage> = messages.Messages;
messages.getDialogs#a0f4cb4f flags:# exclude_pinned:flags.0?true folder_id:flags.1?int offset_date:int offset_id:int offset_peer:InputPeer limit:int hash:long = messages.Dialogs;
messages.getHistory#4423e6c5 peer:InputPeer offset_id:int offset_date:int add_offset:int limit:int max_id:int min_id:int hash:long = messages.Messages;
messages.search#29ee847a flags:# peer:InputPeer q:string from_id:flags.0?InputPeer saved_peer_id:flags.2?InputPeer saved_reaction:flags.3?Vector<Reaction> top_msg_id:flags.1?int filter:MessagesFilter min_date:int max_date:int offset_id:int add_offset:int limit:int max_id:int min_id:int hash:long = messages.Messages;
messages.readHistory#e306d3a peer:InputPeer max_id:int = messages.AffectedMessages;
messages.deleteHistory#b08f922a flags:# just_clear:flags.0?true revoke:flags.1?true peer:InputPeer max_id:int min_date:flags.2?int max_date:flags.3?int = messages.AffectedHistory;
messages.deleteMessages#e58e95d2 flags:# revoke:flags.0?true id:Vector<int> = messages.AffectedMessages;
messages.receivedMessages#5a954c0 max_id:int = Vector<ReceivedNotifyMessage>;
messages.setTyping#58943ee2 flags:# peer:InputPeer top_msg_id:flags.0?int action:SendMessageAction = Bool;
messages.sendMessage#fe05dc9a flags:# no_webpage:flags.1?true silent:flags.5?true background:flags.6?true clear_draft:flags.7?true noforwards:flags.14?true update_stickersets_order:flags.15?true invert_media:flags.16?true allow_paid_floodskip:flags.19?true peer:InputPeer reply_to:flags.0?InputReplyTo message:string random_id:long reply_markup:flags.2?ReplyMarkup entities:flags.3?Vector<MessageEntity> schedule_date:flags.10?int send_as:flags.13?InputPeer quick_reply_shortcut:flags.17?InputQuickReplyShortcut effect:flags.18?long allow_paid_stars:flags.21?long suggested_post:flags.22?SuggestedPost = Updates;
messages.sendMedia#ac55d9c1 flags:# silent:flags.5?true background:flags.6?true clear_draft:flags.7?true noforwards:flags.14?true update_stickersets_order:flags.15?true invert_media:flags.16?true allow_paid_floodskip:flags.19?true peer:InputPeer reply_to:flags.0?InputReplyTo media:InputMedia message:string random_id:long reply_markup:flags.2?ReplyMarkup entities:flags.3?Vector<MessageEntity> schedule_date:flags.10?int send_as:flags.13?InputPeer quick_reply_shortcut:flags.17?InputQuickReplyShortcut effect:flags.18?long allow_paid_stars:flags.21?long suggested_post:flags.22?SuggestedPost = Updates;
messages.forwardMessages#978928ca flags:# silent:flags.5?true background:flags.6?true with_my_score:flags.8?true drop_author:flags.11?true drop_media_captions:flags.12?true noforwards:flags.14?true allow_paid_floodskip:flags.19?true from_peer:InputPeer id:Vector<int> random_id:Vector<long> to_peer:InputPeer top_msg_id:flags.9?int reply_to:flags.22?InputReplyTo schedule_date:flags.10?int send_as:flags.13?InputPeer quick_reply_shortcut:flags.17?InputQuickReplyShortcut video_timestamp:flags.20?int allow_paid_stars:flags.21?long suggested_post:flags.23?SuggestedPost = Updates;
messages.reportSpam#cf1592db peer:InputPeer = Bool;
messages.getPeerSettings#efd9a6a2 peer:InputPeer = messages.PeerSettings;
messages.report#fc78af9b peer:InputPeer id:Vector<int> option:bytes message:string = ReportResult;
messages.getChats#49e9528f id:Vector<long> = messages.Chats;
messages.getFullChat#aeb00b34 chat_id:long = messages.ChatFull;
messages.editChatTitle#73783ffd chat_id:long title:string = Updates;
messages.editChatPhoto#35ddd674 chat_id:long photo:InputChatPhoto = Updates;
messages.addChatUser#cbc6d107 chat_id:long user_id:InputUser fwd_limit:int = messages.InvitedUsers;
messages.deleteChatUser#a2185cab flags:# revoke_history:flags.0?true chat_id:long user_id:InputUser = Updates;
messages.createChat#92ceddd4 flags:# users:Vector<InputUser> title:string ttl_period:flags.0?int = messages.InvitedUsers;
messages.getDhConfig#26cf8950 version:int random_length:int = messages.DhConfig;
messages.requestEncryption#f64daf43 user_id:InputUser random_id:int g_a:bytes = EncryptedChat;
messages.acceptEncryption#3dbc0415 peer:InputEncryptedChat g_b:bytes key_fingerprint:long = EncryptedChat;
messages.discardEncryption#f393aea0 flags:# delete_history:flags.0?true chat_id:int = Bool;
messages.setEncryptedTyping#791451ed peer:InputEncryptedChat typing:Bool = Bool;
messages.readEncryptedHistory#7f4b690a peer:InputEncryptedChat max_date:int = Bool;
messages.sendEncrypted#44fa7a15 flags:# silent:flags.0?true peer:InputEncryptedChat random_id:long data:bytes = messages.SentEncryptedMessage;
messages.sendEncryptedFile#5559481d flags:# silent:flags.0?true peer:InputEncryptedChat random_id:long data:bytes file:InputEncryptedFile = messages.SentEncryptedMessage;
messages.sendEncryptedService#32d439a4 peer:InputEncryptedChat random_id:long data:bytes = messages.SentEncryptedMessage;
messages.receivedQueue#55a5bb66 max_qts:int = Vector<long>;
messages.reportEncryptedSpam#4b0c8c0f peer:InputEncryptedChat = Bool;
messages.readMessageContents#36a73f77 id:Vector<int> = messages.AffectedMessages;
messages.getStickers#d5a5d3a1 emoticon:string hash:long = messages.Stickers;
messages.getAllStickers#b8a0a1a8 hash:long = messages.AllStickers;
messages.getWebPagePreview#570d6f6f flags:# message:string entities:flags.3?Vector<MessageEntity> = messages.WebPagePreview;
messages.exportChatInvite#a455de90 flags:# legacy_revoke_permanent:flags.2?true request_needed:flags.3?true peer:InputPeer expire_date:flags.0?int usage_limit:flags.1?int title:flags.4?string subscription_pricing:flags.5?StarsSubscriptionPricing = ExportedChatInvite;
messages.checkChatInvite#3eadb1bb hash:string = ChatInvite;
messages.importChatInvite#6c50051c hash:string = Updates;
messages.getStickerSet#c8a0ec74 stickerset:InputStickerSet hash:int = messages.StickerSet;
messages.installStickerSet#c78fe460 stickerset:InputStickerSet archived:Bool = messages.StickerSetInstallResult;
messages.uninstallStickerSet#f96e55de stickerset:InputStickerSet = Bool;
messages.startBot#e6df7378 bot:InputUser peer:InputPeer random_id:long start_param:string = Updates;
messages.getMessagesViews#5784d3e1 peer:InputPeer id:Vector<int> increment:Bool = messages.MessageViews;
messages.editChatAdmin#a85bd1c2 chat_id:long user_id:InputUser is_admin:Bool = Bool;
messages.migrateChat#a2875319 chat_id:long = Updates;
messages.searchGlobal#4bc6589a flags:# broadcasts_only:flags.1?true groups_only:flags.2?true users_only:flags.3?true folder_id:flags.0?int q:string filter:MessagesFilter min_date:int max_date:int offset_rate:int offset_peer:InputPeer offset_id:int limit:int = messages.Messages;
messages.reorderStickerSets#78337739 flags:# masks:flags.0?true emojis:flags.1?true order:Vector<long> = Bool;
messages.getDocumentByHash#b1f2061f sha256:bytes size:long mime_type:string = Document;
messages.getSavedGifs#5cf09635 hash:long = messages.SavedGifs;
messages.saveGif#327a30cb id:InputDocument unsave:Bool = Bool;
messages.getInlineBotResults#514e999d flags:# bot:InputUser peer:InputPeer geo_point:flags.0?InputGeoPoint query:string offset:string = messages.BotResults;
messages.setInlineBotResults#bb12a419 flags:# gallery:flags.0?true private:flags.1?true query_id:long results:Vector<InputBotInlineResult> cache_time:int next_offset:flags.2?string switch_pm:flags.3?InlineBotSwitchPM switch_webview:flags.4?InlineBotWebView = Bool;
messages.sendInlineBotResult#c0cf7646 flags:# silent:flags.5?true background:flags.6?true clear_draft:flags.7?true hide_via:flags.11?true peer:InputPeer reply_to:flags.0?InputReplyTo random_id:long query_id:long id:string schedule_date:flags.10?int send_as:flags.13?InputPeer quick_reply_shortcut:flags.17?InputQuickReplyShortcut allow_paid_stars:flags.21?long = Updates;
messages.getMessageEditData#fda68d36 peer:InputPeer id:int = messages.MessageEditData;
messages.editMessage#dfd14005 flags:# no_webpage:flags.1?true invert_media:flags.16?true peer:InputPeer id:int message:flags.11?string media:flags.14?InputMedia reply_markup:flags.2?ReplyMarkup entities:flags.3?Vector<MessageEntity> schedule_date:flags.15?int quick_reply_shortcut_id:flags.17?int = Updates;
messages.editInlineBotMessage#83557dba flags:# no_webpage:flags.1?true invert_media:flags.16?true id:InputBotInlineMessageID message:flags.11?string media:flags.14?InputMedia reply_markup:flags.2?ReplyMarkup entities:flags.3?Vector<MessageEntity> = Bool;
messages.getBotCallbackAnswer#9342ca07 flags:# game:flags.1?true peer:InputPeer msg_id:int data:flags.0?bytes password:flags.2?InputCheckPasswordSRP = messages.BotCallbackAnswer;
messages.setBotCallbackAnswer#d58f130a flags:# alert:flags.1?true query_id:long message:flags.0?string url:flags.2?string cache_time:int = Bool;
messages.getPeerDialogs#e470bcfd peers:Vector<InputDialogPeer> = messages.PeerDialogs;
messages.saveDraft#54ae308e flags:# no_webpage:flags.1?true invert_media:flags.6?true reply_to:flags.4?InputReplyTo peer:InputPeer message:string entities:flags.3?Vector<MessageEntity> media:flags.5?InputMedia effect:flags.7?long suggested_post:flags.8?SuggestedPost = Bool;
messages.getAllDrafts#6a3f8d65 = Updates;
messages.getFeaturedStickers#64780b14 hash:long = messages.FeaturedStickers;
messages.readFeaturedStickers#5b118126 id:Vector<long> = Bool;
messages.getRecentStickers#9da9403b flags:# attached:flags.0?true hash:long = messages.RecentStickers;
messages.saveRecentSticker#392718f8 flags:# attached:flags.0?true id:InputDocument unsave:Bool = Bool;
messages.clearRecentStickers#8999602d flags:# attached:flags.0?true = Bool;
messages.getArchivedStickers#57f17692 flags:# masks:flags.0?true emojis:flags.1?true offset_id:long limit:int = messages.ArchivedStickers;
messages.getMaskStickers#640f82b8 hash:long = messages.AllStickers;
messages.getAttachedStickers#cc5b67cc media:InputStickeredMedia = Vector<StickerSetCovered>;
messages.setGameScore#8ef8ecc0 flags:# edit_message:flags.0?true force:flags.1?true peer:InputPeer id:int user_id:InputUser score:int = Updates;
messages.setInlineGameScore#15ad9f64 flags:# edit_message:flags.0?true force:flags.1?true id:InputBotInlineMessageID user_id:InputUser score:int = Bool;
messages.getGameHighScores#e822649d peer:InputPeer id:int user_id:InputUser = messages.HighScores;
messages.getInlineGameHighScores#f635e1b id:InputBotInlineMessageID user_id:InputUser = messages.HighScores;
messages.getCommonChats#e40ca104 user_id:InputUser max_id:long limit:int = messages.Chats;
messages.getWebPage#8d9692a3 url:string hash:int = messages.WebPage;
messages.toggleDialogPin#a731e257 flags:# pinned:flags.0?true peer:InputDialogPeer = Bool;
messages.reorderPinnedDialogs#3b1adf37 flags:# force:flags.0?true folder_id:int order:Vector<InputDialogPeer> = Bool;
messages.getPinnedDialogs#d6b94df2 folder_id:int = messages.PeerDialogs;
messages.setBotShippingResults#e5f672fa flags:# query_id:long error:flags.0?string shipping_options:flags.1?Vector<ShippingOption> = Bool;
messages.setBotPrecheckoutResults#9c2dd95 flags:# success:flags.1?true query_id:long error:flags.0?string = Bool;
messages.uploadMedia#14967978 flags:# business_connection_id:flags.0?string peer:InputPeer media:InputMedia = MessageMedia;
messages.sendScreenshotNotification#a1405817 peer:InputPeer reply_to:InputReplyTo random_id:long = Updates;
messages.getFavedStickers#4f1aaa9 hash:long = messages.FavedStickers;
messages.faveSticker#b9ffc55b id:InputDocument unfave:Bool = Bool;
messages.getUnreadMentions#f107e790 flags:# peer:InputPeer top_msg_id:flags.0?int offset_id:int add_offset:int limit:int max_id:int min_id:int = messages.Messages;
messages.readMentions#36e5bf4d flags:# peer:InputPeer top_msg_id:flags.0?int = messages.AffectedHistory;
messages.getRecentLocations#702a40e0 peer:InputPeer limit:int hash:long = messages.Messages;
messages.sendMultiMedia#1bf89d74 flags:# silent:flags.5?true background:flags.6?true clear_draft:flags.7?true noforwards:flags.14?true update_stickersets_order:flags.15?true invert_media:flags.16?true allow_paid_floodskip:flags.19?true peer:InputPeer reply_to:flags.0?InputReplyTo multi_media:Vector<InputSingleMedia> schedule_date:flags.10?int send_as:flags.13?InputPeer quick_reply_shortcut:flags.17?InputQuickReplyShortcut effect:flags.18?long allow_paid_stars:flags.21?long = Updates;
messages.uploadEncryptedFile#5057c497 peer:InputEncryptedChat file:InputEncryptedFile = EncryptedFile;
messages.searchStickerSets#35705b8a flags:# exclude_featured:flags.0?true q:string hash:long = messages.FoundStickerSets;
messages.getSplitRanges#1cff7e08 = Vector<MessageRange>;
messages.markDialogUnread#8c5006f8 flags:# unread:flags.0?true parent_peer:flags.1?InputPeer peer:InputDialogPeer = Bool;
messages.getDialogUnreadMarks#21202222 flags:# parent_peer:flags.0?InputPeer = Vector<DialogPeer>;
messages.clearAllDrafts#7e58ee9c = Bool;
messages.updatePinnedMessage#d2aaf7ec flags:# silent:flags.0?true unpin:flags.1?true pm_oneside:flags.2?true peer:InputPeer id:int = Updates;
messages.sendVote#10ea6184 peer:InputPeer msg_id:int options:Vector<bytes> = Updates;
messages.getPollResults#73bb643b peer:InputPeer msg_id:int = Updates;
messages.getOnlines#6e2be050 peer:InputPeer = ChatOnlines;
messages.editChatAbout#def60797 peer:InputPeer about:string = Bool;
messages.editChatDefaultBannedRights#a5866b41 peer:InputPeer banned_rights:ChatBannedRights = Updates;
messages.getEmojiKeywords#35a0e062 lang_code:string = EmojiKeywordsDifference;
messages.getEmojiKeywordsDifference#1508b6af lang_code:string from_version:int = EmojiKeywordsDifference;
messages.getEmojiKeywordsLanguages#4e9963b2 lang_codes:Vector<string> = Vector<EmojiLanguage>;
messages.getEmojiURL#d5b10c26 lang_code:string = EmojiURL;
messages.getSearchCounters#1bbcf300 flags:# peer:InputPeer saved_peer_id:flags.2?InputPeer top_msg_id:flags.0?int filters:Vector<MessagesFilter> = Vector<messages.SearchCounter>;
messages.requestUrlAuth#198fb446 flags:# peer:flags.1?InputPeer msg_id:flags.1?int button_id:flags.1?int url:flags.2?string = UrlAuthResult;
messages.acceptUrlAuth#b12c7125 flags:# write_allowed:flags.0?true peer:flags.1?InputPeer msg_id:flags.1?int button_id:flags.1?int url:flags.2?string = UrlAuthResult;
messages.hidePeerSettingsBar#4facb138 peer:InputPeer = Bool;
messages.getScheduledHistory#f516760b peer:InputPeer hash:long = messages.Messages;
messages.getScheduledMessages#bdbb0464 peer:InputPeer id:Vector<int> = messages.Messages;
messages.sendScheduledMessages#bd38850a peer:InputPeer id:Vector<int> = Updates;
messages.deleteScheduledMessages#59ae2b16 peer:InputPeer id:Vector<int> = Updates;
messages.getPollVotes#b86e380e flags:# peer:InputPeer id:int option:flags.0?bytes offset:flags.1?string limit:int = messages.VotesList;
messages.toggleStickerSets#b5052fea flags:# uninstall:flags.0?true archive:flags.1?true unarchive:flags.2?true stickersets:Vector<InputStickerSet> = Bool;
messages.getDialogFilters#efd48c89 = messages.DialogFilters;
messages.getSuggestedDialogFilters#a29cd42c = Vector<DialogFilterSuggested>;
messages.updateDialogFilter#1ad4a04a flags:# id:int filter:flags.0?DialogFilter = Bool;
messages.updateDialogFiltersOrder#c563c1e4 order:Vector<int> = Bool;
messages.getOldFeaturedStickers#7ed094a1 offset:int limit:int hash:long = messages.FeaturedStickers;
messages.getReplies#22ddd30c peer:InputPeer msg_id:int offset_id:int offset_date:int add_offset:int limit:int max_id:int min_id:int hash:long = messages.Messages;
messages.getDiscussionMessage#446972fd peer:InputPeer msg_id:int = messages.DiscussionMessage;
messages.readDiscussion#f731a9f4 peer:InputPeer msg_id:int read_max_id:int = Bool;
messages.unpinAllMessages#62dd747 flags:# peer:InputPeer top_msg_id:flags.0?int saved_peer_id:flags.1?InputPeer = messages.AffectedHistory;
messages.deleteChat#5bd0ee50 chat_id:long = Bool;
messages.deletePhoneCallHistory#f9cbe409 flags:# revoke:flags.0?true = messages.AffectedFoundMessages;
messages.checkHistoryImport#43fe19f3 import_head:string = messages.HistoryImportParsed;
messages.initHistoryImport#34090c3b peer:InputPeer file:InputFile media_count:int = messages.HistoryImport;
messages.uploadImportedMedia#2a862092 peer:InputPeer import_id:long file_name:string media:InputMedia = MessageMedia;
messages.startHistoryImport#b43df344 peer:InputPeer import_id:long = Bool;
messages.getExportedChatInvites#a2b5a3f6 flags:# revoked:flags.3?true peer:InputPeer admin_id:InputUser offset_date:flags.2?int offset_link:flags.2?string limit:int = messages.ExportedChatInvites;
messages.getExportedChatInvite#73746f5c peer:InputPeer link:string = messages.ExportedChatInvite;
messages.editExportedChatInvite#bdca2f75 flags:# revoked:flags.2?true peer:InputPeer link:string expire_date:flags.0?int usage_limit:flags.1?int request_needed:flags.3?Bool title:flags.4?string = messages.ExportedChatInvite;
messages.deleteRevokedExportedChatInvites#56987bd5 peer:InputPeer admin_id:InputUser = Bool;
messages.deleteExportedChatInvite#d464a42b peer:InputPeer link:string = Bool;
messages.getAdminsWithInvites#3920e6ef peer:InputPeer = messages.ChatAdminsWithInvites;
messages.getChatInviteImporters#df04dd4e flags:# requested:flags.0?true subscription_expired:flags.3?true peer:InputPeer link:flags.1?string q:flags.2?string offset_date:int offset_user:InputUser limit:int = messages.ChatInviteImporters;
messages.setHistoryTTL#b80e5fe4 peer:InputPeer period:int = Updates;
messages.checkHistoryImportPeer#5dc60f03 peer:InputPeer = messages.CheckedHistoryImportPeer;
messages.setChatTheme#81202c9 peer:InputPeer theme:InputChatTheme = Updates;
messages.getMessageReadParticipants#31c1c44f peer:InputPeer msg_id:int = Vector<ReadParticipantDate>;
messages.getSearchResultsCalendar#6aa3f6bd flags:# peer:InputPeer saved_peer_id:flags.2?InputPeer filter:MessagesFilter offset_id:int offset_date:int = messages.SearchResultsCalendar;
messages.getSearchResultsPositions#9c7f2f10 flags:# peer:InputPeer saved_peer_id:flags.2?InputPeer filter:MessagesFilter offset_id:int limit:int = messages.SearchResultsPositions;
messages.hideChatJoinRequest#7fe7e815 flags:# approved:flags.0?true peer:InputPeer user_id:InputUser = Updates;
messages.hideAllChatJoinRequests#e085f4ea flags:# approved:flags.0?true peer:InputPeer link:flags.1?string = Updates;
messages.toggleNoForwards#b11eafa2 peer:InputPeer enabled:Bool = Updates;
messages.saveDefaultSendAs#ccfddf96 peer:InputPeer send_as:InputPeer = Bool;
messages.sendReaction#d30d78d4 flags:# big:flags.1?true add_to_recent:flags.2?true peer:InputPeer msg_id:int reaction:flags.0?Vector<Reaction> = Updates;
messages.getMessagesReactions#8bba90e6 peer:InputPeer id:Vector<int> = Updates;
messages.getMessageReactionsList#461b3f48 flags:# peer:InputPeer id:int reaction:flags.0?Reaction offset:flags.1?string limit:int = messages.MessageReactionsList;
messages.setChatAvailableReactions#864b2581 flags:# peer:InputPeer available_reactions:ChatReactions reactions_limit:flags.0?int paid_enabled:flags.1?Bool = Updates;
messages.getAvailableReactions#18dea0ac hash:int = messages.AvailableReactions;
messages.setDefaultReaction#4f47a016 reaction:Reaction = Bool;
messages.translateText#63183030 flags:# peer:flags.0?InputPeer id:flags.0?Vector<int> text:flags.1?Vector<TextWithEntities> to_lang:string = messages.TranslatedText;
messages.getUnreadReactions#bd7f90ac flags:# peer:InputPeer top_msg_id:flags.0?int saved_peer_id:flags.1?InputPeer offset_id:int add_offset:int limit:int max_id:int min_id:int = messages.Messages;
messages.readReactions#9ec44f93 flags:# peer:InputPeer top_msg_id:flags.0?int saved_peer_id:flags.1?InputPeer = messages.AffectedHistory;
messages.searchSentMedia#107e31a0 q:string filter:MessagesFilter limit:int = messages.Messages;
messages.getAttachMenuBots#16fcc2cb hash:long = AttachMenuBots;
messages.getAttachMenuBot#77216192 bot:InputUser = AttachMenuBotsBot;
messages.toggleBotInAttachMenu#69f59d69 flags:# write_allowed:flags.0?true bot:InputUser enabled:Bool = Bool;
messages.requestWebView#269dc2c1 flags:# from_bot_menu:flags.4?true silent:flags.5?true compact:flags.7?true fullscreen:flags.8?true peer:InputPeer bot:InputUser url:flags.1?string start_param:flags.3?string theme_params:flags.2?DataJSON platform:string reply_to:flags.0?InputReplyTo send_as:flags.13?InputPeer = WebViewResult;
messages.prolongWebView#b0d81a83 flags:# silent:flags.5?true peer:InputPeer bot:InputUser query_id:long reply_to:flags.0?InputReplyTo send_as:flags.13?InputPeer = Bool;
messages.requestSimpleWebView#413a3e73 flags:# from_switch_webview:flags.1?true from_side_menu:flags.2?true compact:flags.7?true fullscreen:flags.8?true bot:InputUser url:flags.3?string start_param:flags.4?string theme_params:flags.0?DataJSON platform:string = WebViewResult;
messages.sendWebViewResultMessage#a4314f5 bot_query_id:string result:InputBotInlineResult = WebViewMessageSent;
messages.sendWebViewData#dc0242c8 bot:InputUser random_id:long button_text:string data:string = Updates;
messages.transcribeAudio#269e9a49 peer:InputPeer msg_id:int = messages.TranscribedAudio;
messages.rateTranscribedAudio#7f1d072f peer:InputPeer msg_id:int transcription_id:long good:Bool = Bool;
messages.getCustomEmojiDocuments#d9ab0f54 document_id:Vector<long> = Vector<Document>;
messages.getEmojiStickers#fbfca18f hash:long = messages.AllStickers;
messages.getFeaturedEmojiStickers#ecf6736 hash:long = messages.FeaturedStickers;
messages.reportReaction#3f64c076 peer:InputPeer id:int reaction_peer:InputPeer = Bool;
messages.getTopReactions#bb8125ba limit:int hash:long = messages.Reactions;
messages.getRecentReactions#39461db2 limit:int hash:long = messages.Reactions;
messages.clearRecentReactions#9dfeefb4 = Bool;
messages.getExtendedMedia#84f80814 peer:InputPeer id:Vector<int> = Updates;
messages.setDefaultHistoryTTL#9eb51445 period:int = Bool;
messages.getDefaultHistoryTTL#658b7188 = DefaultHistoryTTL;
messages.sendBotRequestedPeer#91b2d060 peer:InputPeer msg_id:int button_id:int requested_peers:Vector<InputPeer> = Updates;
messages.getEmojiGroups#7488ce5b hash:int = messages.EmojiGroups;
messages.getEmojiStatusGroups#2ecd56cd hash:int = messages.EmojiGroups;
messages.getEmojiProfilePhotoGroups#21a548f3 hash:int = messages.EmojiGroups;
messages.searchCustomEmoji#2c11c0d7 emoticon:string hash:long = EmojiList;
messages.togglePeerTranslations#e47cb579 flags:# disabled:flags.0?true peer:InputPeer = Bool;
messages.getBotApp#34fdc5c3 app:InputBotApp hash:long = messages.BotApp;
messages.requestAppWebView#53618bce flags:# write_allowed:flags.0?true compact:flags.7?true fullscreen:flags.8?true peer:InputPeer app:InputBotApp start_param:flags.1?string theme_params:flags.2?DataJSON platform:string = WebViewResult;
messages.setChatWallPaper#8ffacae1 flags:# for_both:flags.3?true revert:flags.4?true peer:InputPeer wallpaper:flags.0?InputWallPaper settings:flags.2?WallPaperSettings id:flags.1?int = Updates;
messages.searchEmojiStickerSets#92b4494c flags:# exclude_featured:flags.0?true q:string hash:long = messages.FoundStickerSets;
messages.getSavedDialogs#1e91fc99 flags:# exclude_pinned:flags.0?true parent_peer:flags.1?InputPeer offset_date:int offset_id:int offset_peer:InputPeer limit:int hash:long = messages.SavedDialogs;
messages.getSavedHistory#998ab009 flags:# parent_peer:flags.0?InputPeer peer:InputPeer offset_id:int offset_date:int add_offset:int limit:int max_id:int min_id:int hash:long = messages.Messages;
messages.deleteSavedHistory#4dc5085f flags:# parent_peer:flags.0?InputPeer peer:InputPeer max_id:int min_date:flags.2?int max_date:flags.3?int = messages.AffectedHistory;
messages.getPinnedSavedDialogs#d63d94e0 = messages.SavedDialogs;
messages.toggleSavedDialogPin#ac81bbde flags:# pinned:flags.0?true peer:InputDialogPeer = Bool;
messages.reorderPinnedSavedDialogs#8b716587 flags:# force:flags.0?true order:Vector<InputDialogPeer> = Bool;
messages.getSavedReactionTags#3637e05b flags:# peer:flags.0?InputPeer hash:long = messages.SavedReactionTags;
messages.updateSavedReactionTag#60297dec flags:# reaction:Reaction title:flags.0?string = Bool;
messages.getDefaultTagReactions#bdf93428 hash:long = messages.Reactions;
messages.getOutboxReadDate#8c4bfe5d peer:InputPeer msg_id:int = OutboxReadDate;
messages.getQuickReplies#d483f2a8 hash:long = messages.QuickReplies;
messages.reorderQuickReplies#60331907 order:Vector<int> = Bool;
messages.checkQuickReplyShortcut#f1d0fbd3 shortcut:string = Bool;
messages.editQuickReplyShortcut#5c003cef shortcut_id:int shortcut:string = Bool;
messages.deleteQuickReplyShortcut#3cc04740 shortcut_id:int = Bool;
messages.getQuickReplyMessages#94a495c3 flags:# shortcut_id:int id:flags.0?Vector<int> hash:long = messages.Messages;
messages.sendQuickReplyMessages#6c750de1 peer:InputPeer shortcut_id:int id:Vector<int> random_id:Vector<long> = Updates;
messages.deleteQuickReplyMessages#e105e910 shortcut_id:int id:Vector<int> = Updates;
messages.toggleDialogFilterTags#fd2dda49 enabled:Bool = Bool;
messages.getMyStickers#d0b5e1fc offset_id:long limit:int = messages.MyStickers;
messages.getEmojiStickerGroups#1dd840f5 hash:int = messages.EmojiGroups;
messages.getAvailableEffects#dea20a39 hash:int = messages.AvailableEffects;
messages.editFactCheck#589ee75 peer:InputPeer msg_id:int text:TextWithEntities = Updates;
messages.deleteFactCheck#d1da940c peer:InputPeer msg_id:int = Updates;
messages.getFactCheck#b9cdc5ee peer:InputPeer msg_id:Vector<int> = Vector<FactCheck>;
messages.requestMainWebView#c9e01e7b flags:# compact:flags.7?true fullscreen:flags.8?true peer:InputPeer bot:InputUser start_param:flags.1?string theme_params:flags.0?DataJSON platform:string = WebViewResult;
messages.sendPaidReaction#58bbcb50 flags:# peer:InputPeer msg_id:int count:int random_id:long private:flags.0?PaidReactionPrivacy = Updates;
messages.togglePaidReactionPrivacy#435885b5 peer:InputPeer msg_id:int private:PaidReactionPrivacy = Bool;
messages.getPaidReactionPrivacy#472455aa = Updates;
messages.viewSponsoredMessage#269e3643 random_id:bytes = Bool;
messages.clickSponsoredMessage#8235057e flags:# media:flags.0?true fullscreen:flags.1?true random_id:bytes = Bool;
messages.reportSponsoredMessage#12cbf0c4 random_id:bytes option:bytes = channels.SponsoredMessageReportResult;
messages.getSponsoredMessages#3d6ce850 flags:# peer:InputPeer msg_id:flags.0?int = messages.SponsoredMessages;
messages.savePreparedInlineMessage#f21f7f2f flags:# result:InputBotInlineResult user_id:InputUser peer_types:flags.0?Vector<InlineQueryPeerType> = messages.BotPreparedInlineMessage;
messages.getPreparedInlineMessage#857ebdb8 bot:InputUser id:string = messages.PreparedInlineMessage;
messages.searchStickers#29b1c66a flags:# emojis:flags.0?true q:string emoticon:string lang_code:Vector<string> offset:int limit:int hash:long = messages.FoundStickers;
messages.reportMessagesDelivery#5a6d7395 flags:# push:flags.0?true peer:InputPeer id:Vector<int> = Bool;
messages.getSavedDialogsByID#6f6f9c96 flags:# parent_peer:flags.1?InputPeer ids:Vector<InputPeer> = messages.SavedDialogs;
messages.readSavedHistory#ba4a3b5b parent_peer:InputPeer peer:InputPeer max_id:int = Bool;
messages.toggleTodoCompleted#d3e03124 peer:InputPeer msg_id:int completed:Vector<int> incompleted:Vector<int> = Updates;
messages.appendTodoList#21a61057 peer:InputPeer msg_id:int list:Vector<TodoItem> = Updates;
messages.toggleSuggestedPostApproval#8107455c flags:# reject:flags.1?true peer:InputPeer msg_id:int schedule_date:flags.0?int reject_comment:flags.2?string = Updates;

updates.getState#edd4882a = updates.State;
updates.getDifference#19c2f763 flags:# pts:int pts_limit:flags.1?int pts_total_limit:flags.0?int date:int qts:int qts_limit:flags.2?int = updates.Difference;
updates.getChannelDifference#3173d78 flags:# force:flags.0?true channel:InputChannel filter:ChannelMessagesFilter pts:int limit:int = updates.ChannelDifference;

photos.updateProfilePhoto#9e82039 flags:# fallback:flags.0?true bot:flags.1?InputUser id:InputPhoto = photos.Photo;
photos.uploadProfilePhoto#388a3b5 flags:# fallback:flags.3?true bot:flags.5?InputUser file:flags.0?InputFile video:flags.1?InputFile video_start_ts:flags.2?double video_emoji_markup:flags.4?VideoSize = photos.Photo;
photos.deletePhotos#87cf7f2f id:Vector<InputPhoto> = Vector<long>;
photos.getUserPhotos#91cd32a8 user_id:InputUser offset:int max_id:long limit:int = photos.Photos;
photos.uploadContactProfilePhoto#e14c4a71 flags:# suggest:flags.3?true save:flags.4?true user_id:InputUser file:flags.0?InputFile video:flags.1?InputFile video_start_ts:flags.2?double video_emoji_markup:flags.5?VideoSize = photos.Photo;

upload.saveFilePart#b304a621 file_id:long file_part:int bytes:bytes = Bool;
upload.getFile#be5335be flags:# precise:flags.0?true cdn_supported:flags.1?true location:InputFileLocation offset:long limit:int = upload.File;
upload.saveBigFilePart#de7b673d file_id:long file_part:int file_total_parts:int bytes:bytes = Bool;
upload.getWebFile#24e6818d location:InputWebFileLocation offset:int limit:int = upload.WebFile;
upload.getCdnFile#395f69da file_token:bytes offset:long limit:int = upload.CdnFile;
upload.reuploadCdnFile#9b2754a8 file_token:bytes request_token:bytes = Vector<FileHash>;
upload.getCdnFileHashes#91dc3f31 file_token:bytes offset:long = Vector<FileHash>;
upload.getFileHashes#9156982a location:InputFileLocation offset:long = Vector<FileHash>;

help.getConfig#c4f9186b = Config;
help.getNearestDc#1fb33026 = NearestDc;
help.getAppUpdate#522d5a7d source:string = help.AppUpdate;
help.getInviteText#4d392343 = help.InviteText;
help.getSupport#9cdf08cd = help.Support;
help.setBotUpdatesStatus#ec22cfcd pending_updates_count:int message:string = Bool;
help.getCdnConfig#52029342 = CdnConfig;
help.getRecentMeUrls#3dc0f114 referer:string = help.RecentMeUrls;
help.getTermsOfServiceUpdate#2ca51fd1 = help.TermsOfServiceUpdate;
help.acceptTermsOfService#ee72f79a id:DataJSON = Bool;
help.getDeepLinkInfo#3fedc75f path:string = help.DeepLinkInfo;
help.getAppConfig#61e3f854 hash:int = help.AppConfig;
help.saveAppLog#6f02f748 events:Vector<InputAppEvent> = Bool;
help.getPassportConfig#c661ad08 hash:int = help.PassportConfig;
help.getSupportName#d360e72c = help.SupportName;
help.getUserInfo#38a08d3 user_id:InputUser = help.UserInfo;
help.editUserInfo#66b91b70 user_id:InputUser message:string entities:Vector<MessageEntity> = help.UserInfo;
help.getPromoData#c0977421 = help.PromoData;
help.hidePromoData#1e251c95 peer:InputPeer = Bool;
help.dismissSuggestion#f50dbaa1 peer:InputPeer suggestion:string = Bool;
help.getCountriesList#735787a8 lang_code:string hash:int = help.CountriesList;
help.getPremiumPromo#b81b93d4 = help.PremiumPromo;
help.getPeerColors#da80f42f hash:int = help.PeerColors;
help.getPeerProfileColors#abcfa9fd hash:int = help.PeerColors;
help.getTimezonesList#49b30240 hash:int = help.TimezonesList;

channels.readHistory#cc104937 channel:InputChannel max_id:int = Bool;
channels.deleteMessages#84c1fd4e channel:InputChannel id:Vector<int> = messages.AffectedMessages;
channels.reportSpam#f44a8315 channel:InputChannel participant:InputPeer id:Vector<int> = Bool;
channels.getMessages#ad8c9a23 channel:InputChannel id:Vector<InputMessage> = messages.Messages;
channels.getParticipants#77ced9d0 channel:InputChannel filter:ChannelParticipantsFilter offset:int limit:int hash:long = channels.ChannelParticipants;
channels.getParticipant#a0ab6cc6 channel:InputChannel participant:InputPeer = channels.ChannelParticipant;
channels.getChannels#a7f6bbb id:Vector<InputChannel> = messages.Chats;
channels.getFullChannel#8736a09 channel:InputChannel = messages.ChatFull;
channels.createChannel#91006707 flags:# broadcast:flags.0?true megagroup:flags.1?true for_import:flags.3?true forum:flags.5?true title:string about:string geo_point:flags.2?InputGeoPoint address:flags.2?string ttl_period:flags.4?int = Updates;
channels.editAdmin#d33c8902 channel:InputChannel user_id:InputUser admin_rights:ChatAdminRights rank:string = Updates;
channels.editTitle#566decd0 channel:InputChannel title:string = Updates;
channels.editPhoto#f12e57c9 channel:InputChannel photo:InputChatPhoto = Updates;
channels.checkUsername#10e6bd2c channel:InputChannel username:string = Bool;
channels.updateUsername#3514b3de channel:InputChannel username:string = Bool;
channels.joinChannel#24b524c5 channel:InputChannel = Updates;
channels.leaveChannel#f836aa95 channel:InputChannel = Updates;
channels.inviteToChannel#c9e33d54 channel:InputChannel users:Vector<InputUser> = messages.InvitedUsers;
channels.deleteChannel#c0111fe3 channel:InputChannel = Updates;
channels.exportMessageLink#e63fadeb flags:# grouped:flags.0?true thread:flags.1?true channel:InputChannel id:int = ExportedMessageLink;
channels.toggleSignatures#418d549c flags:# signatures_enabled:flags.0?true profiles_enabled:flags.1?true channel:InputChannel = Updates;
channels.getAdminedPublicChannels#f8b036af flags:# by_location:flags.0?true check_limit:flags.1?true for_personal:flags.2?true = messages.Chats;
channels.editBanned#96e6cd81 channel:InputChannel participant:InputPeer banned_rights:ChatBannedRights = Updates;
channels.getAdminLog#33ddf480 flags:# channel:InputChannel q:string events_filter:flags.0?ChannelAdminLogEventsFilter admins:flags.1?Vector<InputUser> max_id:long min_id:long limit:int = channels.AdminLogResults;
channels.setStickers#ea8ca4f9 channel:InputChannel stickerset:InputStickerSet = Bool;
channels.readMessageContents#eab5dc38 channel:InputChannel id:Vector<int> = Bool;
channels.deleteHistory#9baa9647 flags:# for_everyone:flags.0?true channel:InputChannel max_id:int = Updates;
channels.togglePreHistoryHidden#eabbb94c channel:InputChannel enabled:Bool = Updates;
channels.getLeftChannels#8341ecc0 offset:int = messages.Chats;
channels.getGroupsForDiscussion#f5dad378 = messages.Chats;
channels.setDiscussionGroup#40582bb2 broadcast:InputChannel group:InputChannel = Bool;
channels.editCreator#8f38cd1f channel:InputChannel user_id:InputUser password:InputCheckPasswordSRP = Updates;
channels.editLocation#58e63f6d channel:InputChannel geo_point:InputGeoPoint address:string = Bool;
channels.toggleSlowMode#edd49ef0 channel:InputChannel seconds:int = Updates;
channels.getInactiveChannels#11e831ee = messages.InactiveChats;
channels.convertToGigagroup#b290c69 channel:InputChannel = Updates;
channels.getSendAs#e785a43f flags:# for_paid_reactions:flags.0?true peer:InputPeer = channels.SendAsPeers;
channels.deleteParticipantHistory#367544db channel:InputChannel participant:InputPeer = messages.AffectedHistory;
channels.toggleJoinToSend#e4cb9580 channel:InputChannel enabled:Bool = Updates;
channels.toggleJoinRequest#4c2985b6 channel:InputChannel enabled:Bool = Updates;
channels.reorderUsernames#b45ced1d channel:InputChannel order:Vector<string> = Bool;
channels.toggleUsername#50f24105 channel:InputChannel username:string active:Bool = Bool;
channels.deactivateAllUsernames#a245dd3 channel:InputChannel = Bool;
channels.toggleForum#3ff75734 channel:InputChannel enabled:Bool tabs:Bool = Updates;
channels.createForumTopic#f40c0224 flags:# channel:InputChannel title:string icon_color:flags.0?int icon_emoji_id:flags.3?long random_id:long send_as:flags.2?InputPeer = Updates;
channels.getForumTopics#de560d1 flags:# channel:InputChannel q:flags.0?string offset_date:int offset_id:int offset_topic:int limit:int = messages.ForumTopics;
channels.getForumTopicsByID#b0831eb9 channel:InputChannel topics:Vector<int> = messages.ForumTopics;
channels.editForumTopic#f4dfa185 flags:# channel:InputChannel topic_id:int title:flags.0?string icon_emoji_id:flags.1?long closed:flags.2?Bool hidden:flags.3?Bool = Updates;
channels.updatePinnedForumTopic#6c2d9026 channel:InputChannel topic_id:int pinned:Bool = Updates;
channels.deleteTopicHistory#34435f2d channel:InputChannel top_msg_id:int = messages.AffectedHistory;
channels.reorderPinnedForumTopics#2950a18f flags:# force:flags.0?true channel:InputChannel order:Vector<int> = Updates;
channels.toggleAntiSpam#68f3e4eb channel:InputChannel enabled:Bool = Updates;
channels.reportAntiSpamFalsePositive#a850a693 channel:InputChannel msg_id:int = Bool;
channels.toggleParticipantsHidden#6a6e7854 channel:InputChannel enabled:Bool = Updates;
channels.updateColor#d8aa3671 flags:# for_profile:flags.1?true channel:InputChannel color:flags.2?int background_emoji_id:flags.0?long = Updates;
channels.toggleViewForumAsMessages#9738bb15 channel:InputChannel enabled:Bool = Updates;
channels.getChannelRecommendations#25a71742 flags:# channel:flags.0?InputChannel = messages.Chats;
channels.updateEmojiStatus#f0d3e6a8 channel:InputChannel emoji_status:EmojiStatus = Updates;
channels.setBoostsToUnblockRestrictions#ad399cee channel:InputChannel boosts:int = Updates;
channels.setEmojiStickers#3cd930b7 channel:InputChannel stickerset:InputStickerSet = Bool;
channels.restrictSponsoredMessages#9ae91519 channel:InputChannel restricted:Bool = Updates;
channels.searchPosts#f2c4f24d flags:# hashtag:flags.0?string query:flags.1?string offset_rate:int offset_peer:InputPeer offset_id:int limit:int allow_paid_stars:flags.2?long = messages.Messages;
channels.updatePaidMessagesPrice#4b12327b flags:# broadcast_messages_allowed:flags.0?true channel:InputChannel send_paid_messages_stars:long = Updates;
channels.toggleAutotranslation#167fc0a1 channel:InputChannel enabled:Bool = Updates;
channels.getMessageAuthor#ece2a0e6 channel:InputChannel id:int = User;
channels.checkSearchPostsFlood#22567115 flags:# query:flags.0?string = SearchPostsFlood;
channels.setMainProfileTab#3583fcb1 channel:InputChannel tab:ProfileTab = Bool;

bots.sendCustomRequest#aa2769ed custom_method:string params:DataJSON = DataJSON;
bots.answerWebhookJSONQuery#e6213f4d query_id:long data:DataJSON = Bool;
bots.setBotCommands#517165a scope:BotCommandScope lang_code:string commands:Vector<BotCommand> = Bool;
bots.resetBotCommands#3d8de0f9 scope:BotCommandScope lang_code:string = Bool;
bots.getBotCommands#e34c0dd6 scope:BotCommandScope lang_code:string = Vector<BotCommand>;
bots.setBotMenuButton#4504d54f user_id:InputUser button:BotMenuButton = Bool;
bots.getBotMenuButton#9c60eb28 user_id:InputUser = BotMenuButton;
bots.setBotBroadcastDefaultAdminRights#788464e1 admin_rights:ChatAdminRights = Bool;
bots.setBotGroupDefaultAdminRights#925ec9ea admin_rights:ChatAdminRights = Bool;
bots.setBotInfo#10cf3123 flags:# bot:flags.2?InputUser lang_code:string name:flags.3?string about:flags.0?string description:flags.1?string = Bool;
bots.getBotInfo#dcd914fd flags:# bot:flags.0?InputUser lang_code:string = bots.BotInfo;
bots.reorderUsernames#9709b1c2 bot:InputUser order:Vector<string> = Bool;
bots.toggleUsername#53ca973 bot:InputUser username:string active:Bool = Bool;
bots.canSendMessage#1359f4e6 bot:InputUser = Bool;
bots.allowSendMessage#f132e3ef bot:InputUser = Updates;
bots.invokeWebViewCustomMethod#87fc5e7 bot:InputUser custom_method:string params:DataJSON = DataJSON;
bots.getPopularAppBots#c2510192 offset:string limit:int = bots.PopularAppBots;
bots.addPreviewMedia#17aeb75a bot:InputUser lang_code:string media:InputMedia = BotPreviewMedia;
bots.editPreviewMedia#8525606f bot:InputUser lang_code:string media:InputMedia new_media:InputMedia = BotPreviewMedia;
bots.deletePreviewMedia#2d0135b3 bot:InputUser lang_code:string media:Vector<InputMedia> = Bool;
bots.reorderPreviewMedias#b627f3aa bot:InputUser lang_code:string order:Vector<InputMedia> = Bool;
bots.getPreviewInfo#423ab3ad bot:InputUser lang_code:string = bots.PreviewInfo;
bots.getPreviewMedias#a2a5594d bot:InputUser = Vector<BotPreviewMedia>;
bots.updateUserEmojiStatus#ed9f30c5 user_id:InputUser emoji_status:EmojiStatus = Bool;
bots.toggleUserEmojiStatusPermission#6de6392 bot:InputUser enabled:Bool = Bool;
bots.checkDownloadFileParams#50077589 bot:InputUser file_name:string url:string = Bool;
bots.getAdminedBots#b0711d83 = Vector<User>;
bots.updateStarRefProgram#778b5ab3 flags:# bot:InputUser commission_permille:int duration_months:flags.0?int = StarRefProgram;
bots.setCustomVerification#8b89dfbd flags:# enabled:flags.1?true bot:flags.0?InputUser peer:InputPeer custom_description:flags.2?string = Bool;
bots.getBotRecommendations#a1b70815 bot:InputUser = users.Users;

payments.getPaymentForm#37148dbb flags:# invoice:InputInvoice theme_params:flags.0?DataJSON = payments.PaymentForm;
payments.getPaymentReceipt#2478d1cc peer:InputPeer msg_id:int = payments.PaymentReceipt;
payments.validateRequestedInfo#b6c8f12b flags:# save:flags.0?true invoice:InputInvoice info:PaymentRequestedInfo = payments.ValidatedRequestedInfo;
payments.sendPaymentForm#2d03522f flags:# form_id:long invoice:InputInvoice requested_info_id:flags.0?string shipping_option_id:flags.1?string credentials:InputPaymentCredentials tip_amount:flags.2?long = payments.PaymentResult;
payments.getSavedInfo#227d824b = payments.SavedInfo;
payments.clearSavedInfo#d83d70c1 flags:# credentials:flags.0?true info:flags.1?true = Bool;
payments.getBankCardData#2e79d779 number:string = payments.BankCardData;
payments.exportInvoice#f91b065 invoice_media:InputMedia = payments.ExportedInvoice;
payments.assignAppStoreTransaction#80ed747d receipt:bytes purpose:InputStorePaymentPurpose = Updates;
payments.assignPlayMarketTransaction#dffd50d3 receipt:DataJSON purpose:InputStorePaymentPurpose = Updates;
payments.getPremiumGiftCodeOptions#2757ba54 flags:# boost_peer:flags.0?InputPeer = Vector<PremiumGiftCodeOption>;
payments.checkGiftCode#8e51b4c1 slug:string = payments.CheckedGiftCode;
payments.applyGiftCode#f6e26854 slug:string = Updates;
payments.getGiveawayInfo#f4239425 peer:InputPeer msg_id:int = payments.GiveawayInfo;
payments.launchPrepaidGiveaway#5ff58f20 peer:InputPeer giveaway_id:long purpose:InputStorePaymentPurpose = Updates;
payments.getStarsTopupOptions#c00ec7d3 = Vector<StarsTopupOption>;
payments.getStarsStatus#4ea9b3bf flags:# ton:flags.0?true peer:InputPeer = payments.StarsStatus;
payments.getStarsTransactions#69da4557 flags:# inbound:flags.0?true outbound:flags.1?true ascending:flags.2?true ton:flags.4?true subscription_id:flags.3?string peer:InputPeer offset:string limit:int = payments.StarsStatus;
payments.sendStarsForm#7998c914 form_id:long invoice:InputInvoice = payments.PaymentResult;
payments.refundStarsCharge#25ae8f4a user_id:InputUser charge_id:string = Updates;
payments.getStarsRevenueStats#d91ffad6 flags:# dark:flags.0?true ton:flags.1?true peer:InputPeer = payments.StarsRevenueStats;
payments.getStarsRevenueWithdrawalUrl#2433dc92 flags:# ton:flags.0?true peer:InputPeer amount:flags.1?long password:InputCheckPasswordSRP = payments.StarsRevenueWithdrawalUrl;
payments.getStarsRevenueAdsAccountUrl#d1d7efc5 peer:InputPeer = payments.StarsRevenueAdsAccountUrl;
payments.getStarsTransactionsByID#2dca16b8 flags:# ton:flags.0?true peer:InputPeer id:Vector<InputStarsTransaction> = payments.StarsStatus;
payments.getStarsGiftOptions#d3c96bc8 flags:# user_id:flags.0?InputUser = Vector<StarsGiftOption>;
payments.getStarsSubscriptions#32512c5 flags:# missing_balance:flags.0?true peer:InputPeer offset:string = payments.StarsStatus;
payments.changeStarsSubscription#c7770878 flags:# peer:InputPeer subscription_id:string canceled:flags.0?Bool = Bool;
payments.fulfillStarsSubscription#cc5bebb3 peer:InputPeer subscription_id:string = Bool;
payments.getStarsGiveawayOptions#bd1efd3e = Vector<StarsGiveawayOption>;
payments.getStarGifts#c4563590 hash:int = payments.StarGifts;
payments.saveStarGift#2a2a697c flags:# unsave:flags.0?true stargift:InputSavedStarGift = Bool;
payments.convertStarGift#74bf076b stargift:InputSavedStarGift = Bool;
payments.botCancelStarsSubscription#6dfa0622 flags:# restore:flags.0?true user_id:InputUser charge_id:string = Bool;
payments.getConnectedStarRefBots#5869a553 flags:# peer:InputPeer offset_date:flags.2?int offset_link:flags.2?string limit:int = payments.ConnectedStarRefBots;
payments.getConnectedStarRefBot#b7d998f0 peer:InputPeer bot:InputUser = payments.ConnectedStarRefBots;
payments.getSuggestedStarRefBots#d6b48f7 flags:# order_by_revenue:flags.0?true order_by_date:flags.1?true peer:InputPeer offset:string limit:int = payments.SuggestedStarRefBots;
payments.connectStarRefBot#7ed5348a peer:InputPeer bot:InputUser = payments.ConnectedStarRefBots;
payments.editConnectedStarRefBot#e4fca4a3 flags:# revoked:flags.0?true peer:InputPeer link:string = payments.ConnectedStarRefBots;
payments.getStarGiftUpgradePreview#9c9abcb1 gift_id:long = payments.StarGiftUpgradePreview;
payments.upgradeStarGift#aed6e4f5 flags:# keep_original_details:flags.0?true stargift:InputSavedStarGift = Updates;
payments.transferStarGift#7f18176a stargift:InputSavedStarGift to_id:InputPeer = Updates;
payments.getUniqueStarGift#a1974d72 slug:string = payments.UniqueStarGift;
payments.getSavedStarGifts#a319e569 flags:# exclude_unsaved:flags.0?true exclude_saved:flags.1?true exclude_unlimited:flags.2?true exclude_unique:flags.4?true sort_by_value:flags.5?true exclude_upgradable:flags.7?true exclude_unupgradable:flags.8?true peer:InputPeer collection_id:flags.6?int offset:string limit:int = payments.SavedStarGifts;
payments.getSavedStarGift#b455a106 stargift:Vector<InputSavedStarGift> = payments.SavedStarGifts;
payments.getStarGiftWithdrawalUrl#d06e93a8 stargift:InputSavedStarGift password:InputCheckPasswordSRP = payments.StarGiftWithdrawalUrl;
payments.toggleChatStarGiftNotifications#60eaefa1 flags:# enabled:flags.0?true peer:InputPeer = Bool;
payments.toggleStarGiftsPinnedToTop#1513e7b0 peer:InputPeer stargift:Vector<InputSavedStarGift> = Bool;
payments.canPurchaseStore#4fdc5ea7 purpose:InputStorePaymentPurpose = Bool;
payments.getResaleStarGifts#7a5fa236 flags:# sort_by_price:flags.1?true sort_by_num:flags.2?true attributes_hash:flags.0?long gift_id:long attributes:flags.3?Vector<StarGiftAttributeId> offset:string limit:int = payments.ResaleStarGifts;
payments.updateStarGiftPrice#edbe6ccb stargift:InputSavedStarGift resell_amount:StarsAmount = Updates;
payments.createStarGiftCollection#1f4a0e87 peer:InputPeer title:string stargift:Vector<InputSavedStarGift> = StarGiftCollection;
payments.updateStarGiftCollection#4fddbee7 flags:# peer:InputPeer collection_id:int title:flags.0?string delete_stargift:flags.1?Vector<InputSavedStarGift> add_stargift:flags.2?Vector<InputSavedStarGift> order:flags.3?Vector<InputSavedStarGift> = StarGiftCollection;
payments.reorderStarGiftCollections#c32af4cc peer:InputPeer order:Vector<int> = Bool;
payments.deleteStarGiftCollection#ad5648e8 peer:InputPeer collection_id:int = Bool;
payments.getStarGiftCollections#981b91dd peer:InputPeer hash:long = payments.StarGiftCollections;
payments.getUniqueStarGiftValueInfo#4365af6b slug:string = payments.UniqueStarGiftValueInfo;
payments.checkCanSendGift#c0c4edc9 gift_id:long = payments.CheckCanSendGiftResult;

stickers.createStickerSet#9021ab67 flags:# masks:flags.0?true emojis:flags.5?true text_color:flags.6?true user_id:InputUser title:string short_name:string thumb:flags.2?InputDocument stickers:Vector<InputStickerSetItem> software:flags.3?string = messages.StickerSet;
stickers.removeStickerFromSet#f7760f51 sticker:InputDocument = messages.StickerSet;
stickers.changeStickerPosition#ffb6d4ca sticker:InputDocument position:int = messages.StickerSet;
stickers.addStickerToSet#8653febe stickerset:InputStickerSet sticker:InputStickerSetItem = messages.StickerSet;
stickers.setStickerSetThumb#a76a5392 flags:# stickerset:InputStickerSet thumb:flags.0?InputDocument thumb_document_id:flags.1?long = messages.StickerSet;
stickers.checkShortName#284b3639 short_name:string = Bool;
stickers.suggestShortName#4dafc503 title:string = stickers.SuggestedShortName;
stickers.changeSticker#f5537ebc flags:# sticker:InputDocument emoji:flags.0?string mask_coords:flags.1?MaskCoords keywords:flags.2?string = messages.StickerSet;
stickers.renameStickerSet#124b1c00 stickerset:InputStickerSet title:string = messages.StickerSet;
stickers.deleteStickerSet#87704394 stickerset:InputStickerSet = Bool;
stickers.replaceSticker#4696459a sticker:InputDocument new_sticker:InputStickerSetItem = messages.StickerSet;

phone.getCallConfig#55451fa9 = DataJSON;
phone.requestCall#42ff96ed flags:# video:flags.0?true user_id:InputUser random_id:int g_a_hash:bytes protocol:PhoneCallProtocol = phone.PhoneCall;
phone.acceptCall#3bd2b4a0 peer:InputPhoneCall g_b:bytes protocol:PhoneCallProtocol = phone.PhoneCall;
phone.confirmCall#2efe1722 peer:InputPhoneCall g_a:bytes key_fingerprint:long protocol:PhoneCallProtocol = phone.PhoneCall;
phone.receivedCall#17d54f61 peer:InputPhoneCall = Bool;
phone.discardCall#b2cbc1c0 flags:# video:flags.0?true peer:InputPhoneCall duration:int reason:PhoneCallDiscardReason connection_id:long = Updates;
phone.setCallRating#59ead627 flags:# user_initiative:flags.0?true peer:InputPhoneCall rating:int comment:string = Updates;
phone.saveCallDebug#277add7e peer:InputPhoneCall debug:DataJSON = Bool;
phone.sendSignalingData#ff7a9383 peer:InputPhoneCall data:bytes = Bool;
phone.createGroupCall#48cdc6d8 flags:# rtmp_stream:flags.2?true peer:InputPeer random_id:int title:flags.0?string schedule_date:flags.1?int = Updates;
phone.joinGroupCall#8fb53057 flags:# muted:flags.0?true video_stopped:flags.2?true call:InputGroupCall join_as:InputPeer invite_hash:flags.1?string public_key:flags.3?int256 block:flags.3?bytes params:DataJSON = Updates;
phone.leaveGroupCall#500377f9 call:InputGroupCall source:int = Updates;
phone.inviteToGroupCall#7b393160 call:InputGroupCall users:Vector<InputUser> = Updates;
phone.discardGroupCall#7a777135 call:InputGroupCall = Updates;
phone.toggleGroupCallSettings#74bbb43d flags:# reset_invite_hash:flags.1?true call:InputGroupCall join_muted:flags.0?Bool = Updates;
phone.getGroupCall#41845db call:InputGroupCall limit:int = phone.GroupCall;
phone.getGroupParticipants#c558d8ab call:InputGroupCall ids:Vector<InputPeer> sources:Vector<int> offset:string limit:int = phone.GroupParticipants;
phone.checkGroupCall#b59cf977 call:InputGroupCall sources:Vector<int> = Vector<int>;
phone.toggleGroupCallRecord#f128c708 flags:# start:flags.0?true video:flags.2?true call:InputGroupCall title:flags.1?string video_portrait:flags.2?Bool = Updates;
phone.editGroupCallParticipant#a5273abf flags:# call:InputGroupCall participant:InputPeer muted:flags.0?Bool volume:flags.1?int raise_hand:flags.2?Bool video_stopped:flags.3?Bool video_paused:flags.4?Bool presentation_paused:flags.5?Bool = Updates;
phone.editGroupCallTitle#1ca6ac0a call:InputGroupCall title:string = Updates;
phone.getGroupCallJoinAs#ef7c213a peer:InputPeer = phone.JoinAsPeers;
phone.exportGroupCallInvite#e6aa647f flags:# can_self_unmute:flags.0?true call:InputGroupCall = phone.ExportedGroupCallInvite;
phone.toggleGroupCallStartSubscription#219c34e6 call:InputGroupCall subscribed:Bool = Updates;
phone.startScheduledGroupCall#5680e342 call:InputGroupCall = Updates;
phone.saveDefaultGroupCallJoinAs#575e1f8c peer:InputPeer join_as:InputPeer = Bool;
phone.joinGroupCallPresentation#cbea6bc4 call:InputGroupCall params:DataJSON = Updates;
phone.leaveGroupCallPresentation#1c50d144 call:InputGroupCall = Updates;
phone.getGroupCallStreamChannels#1ab21940 call:InputGroupCall = phone.GroupCallStreamChannels;
phone.getGroupCallStreamRtmpUrl#deb3abbf peer:InputPeer revoke:Bool = phone.GroupCallStreamRtmpUrl;
phone.saveCallLog#41248786 peer:InputPhoneCall file:InputFile = Bool;
phone.createConferenceCall#7d0444bb flags:# muted:flags.0?true video_stopped:flags.2?true join:flags.3?true random_id:int public_key:flags.3?int256 block:flags.3?bytes params:flags.3?DataJSON = Updates;
phone.deleteConferenceCallParticipants#8ca60525 flags:# only_left:flags.0?true kick:flags.1?true call:InputGroupCall ids:Vector<long> block:bytes = Updates;
phone.sendConferenceCallBroadcast#c6701900 call:InputGroupCall block:bytes = Updates;
phone.inviteConferenceCallParticipant#bcf22685 flags:# video:flags.0?true call:InputGroupCall user_id:InputUser = Updates;
phone.declineConferenceCallInvite#3c479971 msg_id:int = Updates;
phone.getGroupCallChainBlocks#ee9f88a6 call:InputGroupCall sub_chain_id:int offset:int limit:int = Updates;

langpack.getLangPack#f2f2330a lang_pack:string lang_code:string = LangPackDifference;
langpack.getStrings#efea3803 lang_pack:string lang_code:string keys:Vector<string> = Vector<LangPackString>;
langpack.getDifference#cd984aa5 lang_pack:string lang_code:string from_version:int = LangPackDifference;
langpack.getLanguages#42c6978f lang_pack:string = Vector<LangPackLanguage>;
langpack.getLanguage#6a596502 lang_pack:string lang_code:string = LangPackLanguage;

folders.editPeerFolders#6847d0ab folder_peers:Vector<InputFolderPeer> = Updates;

stats.getBroadcastStats#ab42441a flags:# dark:flags.0?true channel:InputChannel = stats.BroadcastStats;
stats.loadAsyncGraph#621d5fa0 flags:# token:string x:flags.0?long = StatsGraph;
stats.getMegagroupStats#dcdf8607 flags:# dark:flags.0?true channel:InputChannel = stats.MegagroupStats;
stats.getMessagePublicForwards#5f150144 channel:InputChannel msg_id:int offset:string limit:int = stats.PublicForwards;
stats.getMessageStats#b6e0a3f5 flags:# dark:flags.0?true channel:InputChannel msg_id:int = stats.MessageStats;
stats.getStoryStats#374fef40 flags:# dark:flags.0?true peer:InputPeer id:int = stats.StoryStats;
stats.getStoryPublicForwards#a6437ef6 peer:InputPeer id:int offset:string limit:int = stats.PublicForwards;

chatlists.exportChatlistInvite#8472478e chatlist:InputChatlist title:string peers:Vector<InputPeer> = chatlists.ExportedChatlistInvite;
chatlists.deleteExportedInvite#719c5c5e chatlist:InputChatlist slug:string = Bool;
chatlists.editExportedInvite#653db63d flags:# chatlist:InputChatlist slug:string title:flags.1?string peers:flags.2?Vector<InputPeer> = ExportedChatlistInvite;
chatlists.getExportedInvites#ce03da83 chatlist:InputChatlist = chatlists.ExportedInvites;
chatlists.checkChatlistInvite#41c10fff slug:string = chatlists.ChatlistInvite;
chatlists.joinChatlistInvite#a6b1e39a slug:string peers:Vector<InputPeer> = Updates;
chatlists.getChatlistUpdates#89419521 chatlist:InputChatlist = chatlists.ChatlistUpdates;
chatlists.joinChatlistUpdates#e089f8f5 chatlist:InputChatlist peers:Vector<InputPeer> = Updates;
chatlists.hideChatlistUpdates#66e486fb chatlist:InputChatlist = Bool;
chatlists.getLeaveChatlistSuggestions#fdbcd714 chatlist:InputChatlist = Vector<Peer>;
chatlists.leaveChatlist#74fae13a chatlist:InputChatlist peers:Vector<InputPeer> = Updates;

stories.canSendStory#30eb63f0 peer:InputPeer = stories.CanSendStoryCount;
stories.sendStory#737fc2ec flags:# pinned:flags.2?true noforwards:flags.4?true fwd_modified:flags.7?true peer:InputPeer media:InputMedia media_areas:flags.5?Vector<MediaArea> caption:flags.0?string entities:flags.1?Vector<MessageEntity> privacy_rules:Vector<InputPrivacyRule> random_id:long period:flags.3?int fwd_from_id:flags.6?InputPeer fwd_from_story:flags.6?int albums:flags.8?Vector<int> = Updates;
stories.editStory#b583ba46 flags:# peer:InputPeer id:int media:flags.0?InputMedia media_areas:flags.3?Vector<MediaArea> caption:flags.1?string entities:flags.1?Vector<MessageEntity> privacy_rules:flags.2?Vector<InputPrivacyRule> = Updates;
stories.deleteStories#ae59db5f peer:InputPeer id:Vector<int> = Vector<int>;
stories.togglePinned#9a75a1ef peer:InputPeer id:Vector<int> pinned:Bool = Vector<int>;
stories.getAllStories#eeb0d625 flags:# next:flags.1?true hidden:flags.2?true state:flags.0?string = stories.AllStories;
stories.getPinnedStories#5821a5dc peer:InputPeer offset_id:int limit:int = stories.Stories;
stories.getStoriesArchive#b4352016 peer:InputPeer offset_id:int limit:int = stories.Stories;
stories.getStoriesByID#5774ca74 peer:InputPeer id:Vector<int> = stories.Stories;
stories.toggleAllStoriesHidden#7c2557c4 hidden:Bool = Bool;
stories.readStories#a556dac8 peer:InputPeer max_id:int = Vector<int>;
stories.incrementStoryViews#b2028afb peer:InputPeer id:Vector<int> = Bool;
stories.getStoryViewsList#7ed23c57 flags:# just_contacts:flags.0?true reactions_first:flags.2?true forwards_first:flags.3?true peer:InputPeer q:flags.1?string id:int offset:string limit:int = stories.StoryViewsList;
stories.getStoriesViews#28e16cc8 peer:InputPeer id:Vector<int> = stories.StoryViews;
stories.exportStoryLink#7b8def20 peer:InputPeer id:int = ExportedStoryLink;
stories.report#19d8eb45 peer:InputPeer id:Vector<int> option:bytes message:string = ReportResult;
stories.activateStealthMode#57bbd166 flags:# past:flags.0?true future:flags.1?true = Updates;
stories.sendReaction#7fd736b2 flags:# add_to_recent:flags.0?true peer:InputPeer story_id:int reaction:Reaction = Updates;
stories.getPeerStories#2c4ada50 peer:InputPeer = stories.PeerStories;
stories.getAllReadPeerStories#9b5ae7f9 = Updates;
stories.getPeerMaxIDs#535983c3 id:Vector<InputPeer> = Vector<int>;
stories.getChatsToSend#a56a8b60 = messages.Chats;
stories.togglePeerStoriesHidden#bd0415c4 peer:InputPeer hidden:Bool = Bool;
stories.getStoryReactionsList#b9b2881f flags:# forwards_first:flags.2?true peer:InputPeer id:int reaction:flags.0?Reaction offset:flags.1?string limit:int = stories.StoryReactionsList;
stories.togglePinnedToTop#b297e9b peer:InputPeer id:Vector<int> = Bool;
stories.searchPosts#d1810907 flags:# hashtag:flags.0?string area:flags.1?MediaArea peer:flags.2?InputPeer offset:string limit:int = stories.FoundStories;
stories.createAlbum#a36396e5 peer:InputPeer title:string stories:Vector<int> = StoryAlbum;
stories.updateAlbum#5e5259b6 flags:# peer:InputPeer album_id:int title:flags.0?string delete_stories:flags.1?Vector<int> add_stories:flags.2?Vector<int> order:flags.3?Vector<int> = StoryAlbum;
stories.reorderAlbums#8535fbd9 peer:InputPeer order:Vector<int> = Bool;
stories.deleteAlbum#8d3456d0 peer:InputPeer album_id:int = Bool;
stories.getAlbums#25b3eac7 peer:InputPeer hash:long = stories.Albums;
stories.getAlbumStories#ac806d61 peer:InputPeer album_id:int offset:int limit:int = stories.Stories;

premium.getBoostsList#60f67660 flags:# gifts:flags.0?true peer:InputPeer offset:string limit:int = premium.BoostsList;
premium.getMyBoosts#be77b4a = premium.MyBoosts;
premium.applyBoost#6b7da746 flags:# slots:flags.0?Vector<int> peer:InputPeer = premium.MyBoosts;
premium.getBoostsStatus#42f1f61 peer:InputPeer = premium.BoostsStatus;
premium.getUserBoosts#39854d1f peer:InputPeer user_id:InputUser = premium.BoostsList;

smsjobs.isEligibleToJoin#edc39d0 = smsjobs.EligibilityToJoin;
smsjobs.join#a74ece2d = Bool;
smsjobs.leave#9898ad73 = Bool;
smsjobs.updateSettings#93fa0bf flags:# allow_international:flags.0?true = Bool;
smsjobs.getStatus#10a698e8 = smsjobs.Status;
smsjobs.getSmsJob#778d902f job_id:string = SmsJob;
smsjobs.finishJob#4f1ebf24 flags:# job_id:string error:flags.0?string = Bool;

fragment.getCollectibleInfo#be1e85ba collectible:InputCollectible = fragment.CollectibleInfo;
Telegram
Telegram is a cloud-based mobile and desktop messaging app with a focus on security and speed.
About
FAQ
Privacy
Press
Mobile Apps
iPhone/iPad
Android
Mobile Web
Desktop Apps
PC/Mac/Linux
macOS
Web-browser
Platform
API
Translations
Instant View
Go up