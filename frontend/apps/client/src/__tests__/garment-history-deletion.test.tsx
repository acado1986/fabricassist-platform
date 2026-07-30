import type { ReactNode } from 'react';
import { fireEvent, render } from '@testing-library/react-native';
import CustomerHistory from '../app/(customer)/history';

const mockMutate = jest.fn();

jest.mock('../auth/session', () => ({
  useSession: () => ({ apiClient: {}, token: 'access-token' }),
}));

jest.mock('../i18n/TranslationProvider', () => ({
  useTranslation: () => ({
    locale: 'en',
    translate: (key: string) => key,
  }),
}));

jest.mock('../components/FoundationShell', () => ({
  FoundationShell: ({ children }: { children: ReactNode }) => children,
}));

jest.mock('@tanstack/react-query', () => ({
  useMutation: () => ({ isError: false, isPending: false, mutate: mockMutate }),
  useQuery: () => ({
    data: [
      {
        analysed_before: true,
        cleaned_before: false,
        id: '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
        identifiers: ['FA-EXAMPLE'],
        last_analysis_at: null,
        service_events: [],
      },
    ],
    isError: false,
    isLoading: false,
  }),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock('expo-router', () => ({ router: { push: jest.fn() } }));
jest.mock('@expo/vector-icons/Feather', () => 'Feather');

test('history list requires dialog confirmation before deleting a garment history', () => {
  const screen = render(<CustomerHistory />);

  fireEvent.press(screen.getByLabelText('deleteGarment'));

  expect(mockMutate).not.toHaveBeenCalled();
  expect(screen.getByText('deleteGarmentConfirmDescription')).toBeTruthy();

  fireEvent.press(screen.getByLabelText('deleteGarmentConfirmAction'));

  expect(mockMutate).toHaveBeenCalledWith(
    '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
  );
});
