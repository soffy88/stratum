import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LoginForm } from "@/components/auth/LoginForm";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock auth store
const mockLogin = vi.fn();
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ login: mockLogin }),
}));

describe("LoginForm", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders email and password inputs", () => {
    render(<LoginForm />);
    expect(screen.getByPlaceholderText(/邮箱/)).toBeDefined();
    expect(screen.getByPlaceholderText(/密码/)).toBeDefined();
  });

  it("renders submit button", () => {
    render(<LoginForm />);
    expect(screen.getByRole("button", { name: /登录/ })).toBeDefined();
  });

  it("shows validation error on empty submit", async () => {
    render(<LoginForm />);
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => {
      expect(screen.getAllByText(/必填/).length).toBeGreaterThan(0);
    });
  });

  it("calls login on valid submit", async () => {
    mockLogin.mockResolvedValue(undefined);
    render(<LoginForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "pass123" } });
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("a@b.com", "pass123");
    });
  });

  it("shows error message on login failure", async () => {
    mockLogin.mockRejectedValue(new Error("Invalid credentials"));
    render(<LoginForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => {
      expect(screen.getByText(/Invalid credentials/)).toBeDefined();
    });
  });

  it("disables button while submitting", async () => {
    mockLogin.mockImplementation(() => new Promise(() => {})); // never resolves
    render(<LoginForm />);
    fireEvent.change(screen.getByPlaceholderText(/邮箱/), { target: { value: "a@b.com" } });
    fireEvent.change(screen.getByPlaceholderText(/密码/), { target: { value: "pass" } });
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => {
      expect(screen.getByRole("button").getAttribute("disabled")).toBe("");
    });
  });

  it("has password input type=password", () => {
    render(<LoginForm />);
    expect(screen.getByPlaceholderText(/密码/).getAttribute("type")).toBe("password");
  });

  it("form has novalidate by default (uses JS validation)", () => {
    render(<LoginForm />);
    // react-hook-form handles validation, not browser
    expect(screen.getByPlaceholderText(/邮箱/).getAttribute("required")).toBeNull();
  });
});
