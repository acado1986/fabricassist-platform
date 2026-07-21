module.exports = {
  preset: 'jest-expo',
  testMatch: ['<rootDir>/apps/client/src/**/__tests__/**/*.[jt]s?(x)'],
  moduleNameMapper: {
    '^@fabricassist/(.+)$': '<rootDir>/packages/$1/src',
  },
};
