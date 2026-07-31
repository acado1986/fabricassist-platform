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
      '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
      '63b5399e-6c88-47fa-a171-1dc596db4c50',
    ].map((id, index) => ({
      analysed_before: true,
      cleaned_before: false,
      id,
      identifiers: [`FA-EXAMPLE-${index + 1}`],
      last_analysis_at: null,
      service_events: [],
    })),
    isError: false,
    isLoading: false,
  }),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock('expo-router', () => ({ router: { push: jest.fn() } }));
jest.mock('@expo/vector-icons/Feather', () => 'Feather');

test('history list closes the dialog after confirmed garment deletion', async () => {
  const screen = render(<CustomerHistory />);

  const deleteButtons = screen.getAllByLabelText('deleteGarment');
  expect(deleteButtons[0]).toBeDefined();
  fireEvent.press(deleteButtons[0]!);

  expect(mockMutate).not.toHaveBeenCalled();
  expect(screen.getByText('deleteGarmentConfirmDescription')).toBeTruthy();

  fireEvent.press(screen.getByLabelText('deleteGarmentConfirmAction'));

  expect(mockMutate).toHaveBeenCalledWith([
    '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
  ]);
  await waitFor(() => {
    expect(screen.queryByText('deleteGarmentConfirmDescription')).toBeNull();
  });
});

test('history list confirms and deletes multiple selected garment histories', () => {
  const screen = render(<CustomerHistory />);

  fireEvent.press(screen.getByLabelText('selectGarments'));
  const garmentSelectors = screen.getAllByLabelText('selectGarmentForDeletion');
  expect(garmentSelectors).toHaveLength(2);
  fireEvent.press(garmentSelectors[0]!);
  fireEvent.press(garmentSelectors[1]!);

  expect(screen.getByText('selectedGarmentsCount')).toBeTruthy();
  fireEvent.press(screen.getByLabelText('deleteSelectedGarments'));
  expect(screen.getByText('deleteGarmentsConfirmDescription')).toBeTruthy();

  fireEvent.press(screen.getByLabelText('deleteGarmentsConfirmAction'));
  expect(mockMutate).toHaveBeenLastCalledWith([
    '1ee6e701-c7c0-4a3d-a64f-353996a7b1c0',
    '63b5399e-6c88-47fa-a171-1dc596db4c50',
  ]);
});
