import config from '../../app.config';

test('Expo metadata uses FabricAssist canonical names', () => {
  expect(config.name).toBe('FabricAssist');
  expect(config.slug).toBe('fabricassist');
  expect(config.scheme).toBe('fabricassist');
});
