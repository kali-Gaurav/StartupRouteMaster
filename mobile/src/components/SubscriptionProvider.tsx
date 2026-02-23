import React, { createContext, useContext, ReactNode, useEffect } from 'react';
import { useRevenueCat } from '../hooks/useRevenueCat';
import { revenueCatService } from '../services/revenueCatService';

interface SubscriptionContextType {
  isPro: boolean;
  isLoading: boolean;
  customerInfo: any;
  offerings: any;
  purchasePackage: (pack: any) => Promise<boolean>;
  restorePurchases: () => Promise<void>;
}

const SubscriptionContext = createContext<SubscriptionContextType | undefined>(undefined);

export const SubscriptionProvider: React.FC<{ children: ReactNode; appUserId?: string }> = ({ 
  children, 
  appUserId 
}) => {
  const subscriptionData = useRevenueCat();

  useEffect(() => {
    // Initialize the service when provider mounts
    revenueCatService.initialize(appUserId);
  }, [appUserId]);

  return (
    <SubscriptionContext.Provider value={subscriptionData}>
      {children}
    </SubscriptionContext.Provider>
  );
};

export const useSubscription = () => {
  const context = useContext(SubscriptionContext);
  if (context === undefined) {
    throw new Error('useSubscription must be used within a SubscriptionProvider');
  }
  return context;
};
