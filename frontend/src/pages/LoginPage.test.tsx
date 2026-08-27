import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "./LoginPage";
import * as auth from "../auth/AuthContext";

describe("LoginPage", () => {
  it("submits credentials and shows the server error message", async () => {
    const login = vi
      .fn()
      .mockRejectedValueOnce(Object.assign(new Error("Invalid username or password."), {}));
    vi.spyOn(auth, "useAuth").mockReturnValue({
      login,
      me: null,
      loading: false,
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(<LoginPage />);
    await userEvent.type(screen.getByLabelText("Username"), "alice");
    await userEvent.type(screen.getByLabelText("Password"), "secret-value-123");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(login).toHaveBeenCalledWith("alice", "secret-value-123");
    expect(await screen.findByText("Invalid username or password.")).toBeInTheDocument();
  });
});
