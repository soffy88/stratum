import type { Meta, StoryObj } from "@storybook/react";
import { LoginForm } from "@/components/auth/LoginForm";

// Mock next/navigation and stores for Storybook
const meta: Meta<typeof LoginForm> = {
  title: "Auth/LoginForm",
  component: LoginForm,
  parameters: { layout: "centered" },
  decorators: [
    (Story) => (
      <div style={{ width: 400, padding: 24 }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof LoginForm>;

export const Default: Story = {};

export const WithError: Story = {
  parameters: {
    // Simulate a login error state via mock
    nextjs: { router: { push: () => {} } },
  },
};
