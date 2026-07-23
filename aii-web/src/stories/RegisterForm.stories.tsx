import type { Meta, StoryObj } from "@storybook/react";
import { RegisterForm } from "@/components/auth/RegisterForm";

const meta: Meta<typeof RegisterForm> = {
  title: "Auth/RegisterForm",
  component: RegisterForm,
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
type Story = StoryObj<typeof RegisterForm>;

export const Default: Story = {};
