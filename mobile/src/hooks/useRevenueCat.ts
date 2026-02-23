import { useState, useEffect, useCallback } from 'react';
import Purchases, { CustomerInfo, PurchasesOffering, PurchasesPackage } from 'react-native-purchases';
import { revenueCatService, ENTITLEMENT_ID } from '../services/revenueCatService';

export const useRevenueCat = () => {
  const [customerInfo, setCustomerInfo] = useState<CustomerInfo | null>(null);
  const [offerings, setOfferings] = useState<PurchasesOffering | null>(null);
  const [isPro, setIsPro] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const updateStatus = useCallback(async () => {
    try {
      const info = await Purchases.getCustomerInfo();
      setCustomerInfo(info);
      setIsPro(typeof info.entitlements.active[ENTITLEMENT_ID] !== 'undefined');
      
      const currentOfferings = await revenueCatService.getOfferings();
      setOfferings(currentOfferings);
    } catch (e) {
      console.error('Failed to update RevenueCat status:', e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    updateStatus();

    // Listen for changes (e.g. background purchase renewal)
    const listener = (info: CustomerInfo) => {
      setCustomerInfo(info);
      setIsPro(typeof info.entitlements.active[ENTITLEMENT_ID] !== 'undefined');
    };

    Purchases.addCustomerInfoUpdateListener(listener);

    return () => {
      // Cleanup listener if the SDK version supports it, 
      // otherwise listeners are global and persistent.
    };
  }, [updateStatus]);

  const purchasePackage = async (pack: PurchasesPackage) => {
    try {
      const { customerInfo: updatedInfo } = await Purchases.purchasePackage(pack);
      setCustomerInfo(updatedInfo);
      setIsPro(typeof updatedInfo.entitlements.active[ENTITLEMENT_ID] !== 'undefined');
      return true;
    } catch (e: any) {
      if (!e.userCancelled) {
        console.error('Purchase failed:', e);
        throw e;
      }
      return false;
    }
  };

  const restorePurchases = async () => {
    try {
      const info = await revenueCatService.restorePurchases();
      setCustomerInfo(info);
      setIsPro(typeof info.entitlements.active[ENTITLEMENT_ID] !== 'undefined');
    } catch (e) {
      console.error('Restore failed:', e);
      throw e;
    }
  };

  return {
    customerInfo,
    offerings,
    isPro,
    isLoading,
    purchasePackage,
    restorePurchases,
    refreshStatus: updateStatus,
  };
};
