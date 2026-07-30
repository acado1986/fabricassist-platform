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

test('Expo web uses static output and exposes only public deployment settings', () => {
  expect(config.web?.output).toBe('static');
  expect(config.extra).toEqual({
    fabricassistApiPublicUrl: expect.any(String),
    fabricassistEnvironment: expect.any(String),
  });
});
