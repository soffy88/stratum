import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RegisterForm } from "@/components/auth/RegisterForm";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const mockRegister = vi.fn();
const mockLogin = vi.fn();
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ register: mockRegister, login: mockLogin }),
}));

describe("RegisterForm", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders email, username, password inputs", () => {
    render(<RegisterForm />);
    expect(screen.getByPlaceholderText(/邮箱/)).toBeDefined();
    expect(screen.getByPlaceholderText(/用户名/)).toBeDefined();
    expect(screen.getByPlaceholderText(/密码/)).toBeDefined();
  });

  it("renders submit button", () => {
    render(<RegisterForm />);
    expect(screen.getByRole("button", { name: /注册/ })).toBeDefined();
  });

  it("validates email format", async () => {
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "notanemail" } });
    fireEvent.change(screen.getByPlaceholderText(/用户名/), { target: { value: "user1" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "Password123!" } });
    fireEvent.click(screen.getByRole("button", { name: /注册/ }));
    await waitFor(() => {
      expect(screen.getByText(/无效邮箱/)).toBeDefined();
    });
  });

  it("validates username min length", async () => {
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/用户名/), { target: { value: "ab" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "Password123!" } });
    fireEvent.click(screen.getByRole("button", { name: /注册/ }));
    await waitFor(() => {
      expect(screen.getByText(/至少 3/)).toBeDefined();
    });
  });

  it("validates password min length", async () => {
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/用户名/), { target: { value: "user1" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: /注册/ }));
    await waitFor(() => {
      expect(screen.getByText(/至少 10/)).toBeDefined();
    });
  });

  it("calls register then login on valid submit", async () => {
    mockRegister.mockResolvedValue(undefined);
    mockLogin.mockResolvedValue(undefined);
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/用户名/), { target: { value: "user1" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "Password123!" } });
    fireEvent.click(screen.getByRole("button", { name: /注册/ }));
    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith("a@b.com", "user1", "Password123!");
    });
  });

  it("shows error on register failure", async () => {
    mockRegister.mockRejectedValue(new Error("Email taken"));
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/用户名/), { target: { value: "user1" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "Password123!" } });
    fireEvent.click(screen.getByRole("button", { name: /注册/ }));
    await waitFor(() => {
      expect(screen.getByText(/Email taken/)).toBeDefined();
    });
  });

  it("validates username only alphanumeric+underscore", async () => {
    render(<RegisterForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/用户名/), { target: { value: "user name" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "Password123!" } });
    fireEvent.click(screen.getByRole("button", { name: /注册/ }));
    await waitFor(() => {
      expect(screen.getByText(/仅字母数字下划线/)).toBeDefined();
    });
  });
});
