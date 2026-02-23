import React from 'react';
import { StyleSheet, View, ActivityIndicator, Alert } from 'react-native';
import RevenueCatUI, { PAYWALL_RESULT } from 'react-native-purchases-ui';
import { useSubscription } from './SubscriptionProvider';

/**
 * PremiumPaywall Component
 * Presents the RevenueCat-configured paywall to the user.
 * 
 * Documentation: https://www.revenuecat.com/docs/tools/paywalls
 */
export const PremiumPaywall: React.FC<{ onFinished?: () => void }> = ({ onFinished }) => {
  const { refreshStatus } = useSubscription();

  const handlePresentPaywall = async () => {
    try {
      const result = await RevenueCatUI.presentPaywall({
        displayCloseButton: true,
      });

      // Handle paywall outcome
      switch (result) {
        case PAYWALL_RESULT.PURCHASED:
          Alert.alert('Success', 'Welcome to Routemaster Pro!');
          await refreshStatus(); // Refresh status after successful purchase
          onFinished?.();
          break;
        case PAYWALL_RESULT.RESTORED:
          Alert.alert('Success', 'Your purchases have been restored.');
          await refreshStatus();
          onFinished?.();
          break;
        case PAYWALL_RESULT.CANCELLED:
          console.log('User cancelled the paywall');
          onFinished?.();
          break;
        case PAYWALL_RESULT.ERROR:
          Alert.alert('Error', 'There was an error presenting the paywall.');
          onFinished?.();
          break;
      }
    } catch (error) {
      console.error('Error with RevenueCat Paywall:', error);
      Alert.alert('Error', 'Unable to load subscription options.');
    }
  };

  // This can be triggered by a button or automatically
  React.useEffect(() => {
    handlePresentPaywall();
  }, []);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#0000ff" />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
});
