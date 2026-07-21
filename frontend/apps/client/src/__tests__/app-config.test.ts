import config from '../../app.config';

test('Expo metadata uses FabricAssist canonical names', () => {
  expect(config.name).toBe('FabricAssist');
  expect(config.slug).toBe('fabricassist');
  expect(config.scheme).toBe('fabricassist');
});

test('Expo config declares camera permission for device capture', () => {
  expect(config.plugins).toContainEqual([
    'expo-image-picker',
    expect.objectContaining({ cameraPermission: expect.any(String) }),
  ]);
});
