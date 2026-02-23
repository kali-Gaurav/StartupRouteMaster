# 🐱 RevenueCat Integration for Routemaster (React Native)

This guide outlines the steps to integrate the RevenueCat SDK into the Routemaster mobile application for managing subscriptions and "Routemaster Pro" entitlements.

## 1. Installation

Run the following command in your React Native project root:

```bash
npm install --save react-native-purchases react-native-purchases-ui
```

### Android Setup
In `android/app/src/main/AndroidManifest.xml`, ensure you have the billing permission:
```xml
<uses-permission android:name="com.android.vending.BILLING" />
```

### iOS Setup
1. In Xcode, add the `StoreKit` framework to your project.
2. Ensure you have a `Purchases` configuration in your `Info.plist` if required by your version, but usually, the SDK handles it.

## 2. Configuration

We use a singleton service to manage RevenueCat lifecycle.

**Location:** `src/services/revenueCatService.ts`
(See the created file in the codebase)

## 3. Product Configuration

Ensure the following IDs are configured in the RevenueCat Dashboard:

| Product Type | Identifier |
|--------------|------------|
| Monthly      | `monthly`  |
| Yearly       | `yearly`   |
| Lifetime     | `lifetime` |

**Entitlement ID:** `Routemaster Pro`

## 4. Implementation Details

We have provided:
1. **`RevenueCatProvider`**: A React Context provider to wrap your app.
2. **`useRevenueCat`**: A custom hook for checking status and making purchases.
3. **`PaywallScreen`**: A component to show the RevenueCat Paywall.
4. **`CustomerCenter`**: Integration for user self-service.

## 5. Best Practices

- **Initialization**: Initialize early in `App.tsx`.
- **Error Handling**: Always catch and display user-friendly messages for cancelled or failed purchases.
- **Syncing**: The SDK handles syncing with Apple/Google, but you can manually call `restorePurchases()` if needed.
- **Security**: Use the `appUserID` to tie purchases to your backend user accounts.
