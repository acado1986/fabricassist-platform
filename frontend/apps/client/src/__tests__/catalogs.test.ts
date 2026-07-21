import { catalogs } from '@fabricassist/translations';

test('Spanish and English catalogs expose the same shell keys', () => {
  expect(Object.keys(catalogs.es.shell).sort()).toEqual(
    Object.keys(catalogs.en.shell).sort(),
  );
});
