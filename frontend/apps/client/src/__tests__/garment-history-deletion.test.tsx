import type { ReactNode } from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';
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
  useMutation: (options: { onSuccess: () => Promise<void> }) => ({
    isError: false,
    isPending: false,
    mutate: (garmentId: string) => {
      mockMutate(garmentId);
      void options.onSuccess();
    },
  }),
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

test('history list closes the dialog after confirmed garment deletion', async () => {
  const screen = await render(<CustomerHistory />);

  await fireEvent.press(screen.getByLabelText('deleteGarment'));

  expect(mockMutate).not.toHaveBeenCalled();
  expect(screen.getByText('deleteGarmentConfirmDescription')).toBeTruthy();

  await fireEvent.press(screen.getByLabelText('deleteGarmentConfirmAction'));

  expect(mockMutate).toHaveBeenCalledWith(
    '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
  );
  await waitFor(() => {
    expect(screen.queryByText('deleteGarmentConfirmDescription')).toBeNull();
  });
});
