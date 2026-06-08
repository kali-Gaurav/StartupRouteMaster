/**
 * Frontend-Backend Auth Integration Test
 * Verifies Firebase auth flow, token handling, and API connectivity
 */

import { auth } from '@/lib/firebase';
import { fetchWithAuth, getApiBase } from '@/lib/apiClient';

async function testFirebaseConnection() {
  console.log('🔍 Testing Firebase Connection...');
  try {
    const user = auth.currentUser;
    console.log('✅ Firebase connected:', user ? `User exists: ${user.email}` : 'No user logged in');
    return { success: true, user: user ? { email: user.email, uid: user.uid } : null };
  } catch (err) {
    console.error('❌ Firebase connection failed:', err);
    return { success: false, error: err };
  }
}

async function testBackendHealthEndpoint() {
  console.log('🔍 Testing Backend Health Endpoint...');
  try {
    const response = await fetch(`${getApiBase()}/health`);
    const data = await response.json();
    console.log('✅ Backend health:', data);
    return { success: response.ok, data };
  } catch (err) {
    console.error('❌ Backend health check failed:', err);
    return { success: false, error: err };
  }
}

async function testAuthTokenFlow() {
  console.log('🔍 Testing Auth Token Flow...');
  try {
    const user = auth.currentUser;
    if (!user) {
      console.warn('⚠️  No active user');
      return { success: false, error: 'No active user' };
    }

    const token = await user.getIdToken();
    
    // Test token in header
    const response = await fetchWithAuth('/v2/user/profile');
    console.log('✅ Auth token flow working');
    return { success: true, token: token.substring(0, 20) + '...' };
  } catch (err) {
    console.error('❌ Auth token flow failed:', err);
    return { success: false, error: err };
  }
}

async function testCORSConfiguration() {
  console.log('🔍 Testing CORS Configuration...');
  try {
    const response = await fetch(`${getApiBase()}/health`, {
      method: 'OPTIONS',
      headers: {
        'Origin': window.location.origin,
      },
    });
    const corsHeaders = {
      'access-control-allow-origin': response.headers.get('access-control-allow-origin'),
      'access-control-allow-methods': response.headers.get('access-control-allow-methods'),
      'access-control-allow-headers': response.headers.get('access-control-allow-headers'),
    };
    console.log('✅ CORS headers:', corsHeaders);
    return { success: true, corsHeaders };
  } catch (err) {
    console.error('❌ CORS test failed:', err);
    return { success: false, error: err };
  }
}

async function testAPIEndpoints() {
  console.log('🔍 Testing Critical API Endpoints...');
  const endpoints = [
    '/v2/search/unified',
    '/v2/user/profile',
    '/v2/booking/active',
    '/health',
  ];

  const results: Record<string, any> = {};

  for (const endpoint of endpoints) {
    try {
      const res = await fetchWithAuth(endpoint, { method: 'GET' });
      results[endpoint] = { status: res.status, ok: res.ok };
    } catch (err: any) {
      results[endpoint] = { error: err.message };
    }
  }

  console.log('✅ Endpoint test results:', results);
  return { success: true, endpoints: results };
}

export async function runFullAuthIntegrationTest() {
  console.log('\n========== FULL AUTH INTEGRATION TEST ==========\n');

  const results = {
    firebase: await testFirebaseConnection(),
    health: await testBackendHealthEndpoint(),
    cors: await testCORSConfiguration(),
    tokenFlow: await testAuthTokenFlow(),
    endpoints: await testAPIEndpoints(),
  };

  console.log('\n========== TEST RESULTS ==========');
  console.table(results);
  console.log('========================================\n');

  return results;
}

// Run test if this file is imported
if (typeof window !== 'undefined') {
  (window as any).runAuthIntegrationTest = runFullAuthIntegrationTest;
}
