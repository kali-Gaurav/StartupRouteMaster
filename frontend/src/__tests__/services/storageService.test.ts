import { db, storageService } from '@/services/storageService';

// Dexie runs in jsdom environment
// Dexie requires IndexedDB; we only run tests when it's available (browser-like env).
if (typeof indexedDB !== 'undefined') {
  describe('storageService', () => {
    beforeEach(async () => {
      // delete and re-open to reset schema
      await db.delete();
      await db.open();
    });

    afterEach(async () => {
      await db.delete();
    });

    test('favorites schema includes count index and getFavorites orders correctly', async () => {
      // add some favorites manually
      await db.favorites.add({ source: 'A', destination: 'B', count: 2 });
      await db.favorites.add({ source: 'C', destination: 'D', count: 5 });
      await db.favorites.add({ source: 'E', destination: 'F', count: 1 });

      const results = await storageService.getFavorites(10);
      expect(results.length).toBe(3);
      // highest count first
      expect(results[0].count).toBe(5);
      expect(results[1].count).toBe(2);
      expect(results[2].count).toBe(1);
    });
  });
} else {
  test.skip('indexedDB not available, skipping storageService tests', () => {});
}