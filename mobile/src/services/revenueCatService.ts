import { Platform } from 'react-native';
import Purchases, { LOG_LEVEL, PurchasesOffering } from 'react-native-purchases';

const API_KEYS = {
  apple: 'test_WCLwIKeoHULNBeXCmJWRUOxsblQ', // Replace with iOS specific if different
  google: 'test_WCLwIKeoHULNBeXCmJWRUOxsblQ',
};

export const ENTITLEMENT_ID = 'Routemaster Pro';

export class RevenueCatService {
  private static instance: RevenueCatService;

  private constructor() {}

  public static getInstance(): RevenueCatService {
    if (!RevenueCatService.instance) {
      RevenueCatService.instance = new RevenueCatService();
    }
    return RevenueCatService.instance;
  }

  /**
   * Initialize the SDK
   */
  public async initialize(appUserId?: string) {
    Purchases.setLogLevel(LOG_LEVEL.VERBOSE);

    const apiKey = Platform.select({
      ios: API_KEYS.apple,
      android: API_KEYS.google,
    });

    if (!apiKey) {
      console.error('RevenueCat API Key not found for this platform');
      return;
    }

    Purchases.configure({ apiKey, appUserID: appUserId });
    
    // Enable transactional restoring for better customer experience
    await Purchases.enableAdServicesAttributionTokenCollection();
  }

  /**
   * Get current offerings
   */
  public async getOfferings(): Promise<PurchasesOffering | null> {
    try {
      const offerings = await Purchases.getOfferings();
      return offerings.current;
    } catch (e) {
      console.error('Error fetching offerings:', e);
      return null;
    }
  }

  /**
   * Check if user has active entitlement
   */
  public async checkEntitlementStatus(): Promise<boolean> {
    try {
      const customerInfo = await Purchases.getCustomerInfo();
      return typeof customerInfo.entitlements.active[ENTITLEMENT_ID] !== 'undefined';
    } catch (e) {
      console.error('Error checking entitlements:', e);
      return false;
    }
  }

  /**
   * Restore purchases for the user
   */
  public async restorePurchases() {
    try {
      return await Purchases.restorePurchases();
    } catch (e) {
      console.error('Error restoring purchases:', e);
      throw e;
    }
  }
}

export const revenueCatService = RevenueCatService.getInstance();
