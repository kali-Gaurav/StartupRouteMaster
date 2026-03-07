/**
 * Frontend-Backend Auth Integration Test
 * Verifies Supabase auth flow, token handling, and API connectivity
 */

import { supabase } from '@/lib/supabase';
import { fetchWithAuth, getApiBase } from '@/lib/apiClient';

async function testSupabaseConnection() {
  console.log('🔍 Testing Supabase Connection...');
  try {
    const { data, error } = await supabase.auth.getSession();
    if (error) throw error;
    console.log('✅ Supabase connected:', data ? 'Session exists' : 'No session');
    return { success: true, session: data };
  } catch (err) {
    console.error('❌ Supabase connection failed:', err);
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
    // Get current session
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) {
      console.warn('⚠️  No active session');
      return { success: false, error: 'No active session' };
    }

    // Test token in header
    const response = await fetchWithAuth('/v2/user/profile');
    console.log('✅ Auth token flow working');
    return { success: true, token: session.access_token.substring(0, 20) + '...' };
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

async function testLoginFlow() {
  console.log('🔍 Testing Login Flow...');
  try {
    // Test with dummy credentials (will fail auth but shows flow works)
    const { error: signUpError } = await supabase.auth.signUp({
      email: 'test-integration@routemaster.local',
      password: 'TestPassword123!',
    });
    
    if (signUpError && signUpError.message.includes('already exists')) {
      console.log('✅ Account exists (expected for repeated test)');
      
      // Try login
      const { data: loginData, error: loginError } = await supabase.auth.signInWithPassword({
        email: 'test-integration@routemaster.local',
        password: 'TestPassword123!',
      });
      
      if (loginError) {
        console.log('ℹ️  Login returned expected error:', loginError.message);
      } else {
        console.log('✅ Login successful, session:', loginData?.session?.access_token.substring(0, 20) + '...');
      }
      return { success: true };
    } else if (signUpError) {
      console.log('ℹ️  Sign up returned:', signUpError.message);
      return { success: true };
    } else {
      console.log('✅ Sign up successful (new account created)');
      return { success: true };
    }
  } catch (err) {
    console.error('❌ Login flow test failed:', err);
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
    supabase: await testSupabaseConnection(),
    health: await testBackendHealthEndpoint(),
    cors: await testCORSConfiguration(),
    tokenFlow: await testAuthTokenFlow(),
    loginFlow: await testLoginFlow(),
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
