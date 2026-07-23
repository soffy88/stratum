import type { Meta, StoryObj } from "@storybook/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ShareNoteButton } from "@/components/shared/ShareNoteButton";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
});

const meta: Meta<typeof ShareNoteButton> = {
  title: "Shared/ShareNoteButton",
  component: ShareNoteButton,
  parameters: { layout: "centered" },
  decorators: [
    (Story) => (
      <QueryClientProvider client={queryClient}>
        <Story />
      </QueryClientProvider>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof ShareNoteButton>;

export const Default: Story = {
  args: { noteId: "demo-note-id" },
};
