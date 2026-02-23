import React from 'react';
import { View, StyleSheet, Text, TouchableOpacity } from 'react-native';
import RevenueCatUI from 'react-native-purchases-ui';

/**
 * CustomerCenter Integration
 * Allows users to manage their subscriptions, see purchase history, and contact support.
 * 
 * Documentation: https://www.revenuecat.com/docs/tools/customer-center
 */
export const UserCustomerCenter: React.FC = () => {
  const handleOpenCustomerCenter = async () => {
    try {
      await RevenueCatUI.presentCustomerCenter();
    } catch (e) {
      console.error('Failed to present Customer Center:', e);
    }
  };

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Subscription Management</Text>
      <Text style={styles.description}>
        Manage your Routemaster Pro subscription, restore purchases, or contact support.
      </Text>
      <TouchableOpacity 
        style={styles.button} 
        onPress={handleOpenCustomerCenter}
      >
        <Text style={styles.buttonText}>Open Customer Center</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  card: {
    padding: 16,
    margin: 16,
    backgroundColor: '#fff',
    borderRadius: 8,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  title: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  description: {
    fontSize: 14,
    color: '#666',
    marginBottom: 16,
  },
  button: {
    backgroundColor: '#007AFF', // Routemaster blue
    padding: 12,
    borderRadius: 6,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontWeight: '600',
  },
});
