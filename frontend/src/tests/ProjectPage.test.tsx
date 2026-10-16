import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ProjectPage from "@/pages/ProjectPage";
import { apiFetch, getStoredUser, getToken } from "@/lib/api-client";
import type { ApiProjectDetail, Role } from "@/types";

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn(),
  getStoredUser: vi.fn(),
  getToken: vi.fn(),
}));

const mockedApiFetch = apiFetch as unknown as {
  mockImplementation: (
    implementation: (path: string, options?: RequestInit) => Promise<unknown>,
  ) => void;
};

const currentUser = {
  id: "user-1",
  name: "Alex Member",
  email: "alex@example.com",
};

const project: ApiProjectDetail = {
  id: "project-1",
  name: "Launch project",
  description: null,
  ownerId: currentUser.id,
  owner: currentUser,
  memberships: [],
  tasks: [],
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

function renderProjectPage(role: Role) {
  const projectForRole: ApiProjectDetail = {
    ...project,
    memberships: [{
      id: "membership-1",
      role,
      user: currentUser,
    }],
  };
  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "/api/projects/project-1" && !options?.method) {
      return { project: projectForRole };
    }
    return { created: 2, updated: 1, failed: 0 };
  });
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/projects/project-1"]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ProjectPage Airtable export", () => {
  beforeEach(() => {
    vi.mocked(getStoredUser).mockReturnValue(currentUser);
    vi.mocked(getToken).mockReturnValue("test-token");
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it.each(["admin", "member"] as Role[])("allows %s to export tasks", async (role) => {
    renderProjectPage(role);

    fireEvent.click(await screen.findByRole("button", { name: "export to Airtable" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "2 created, 1 updated, 0 failed",
    );
    expect(apiFetch).toHaveBeenCalledWith("/api/projects/project-1/export", {
      method: "POST",
    });
  });

  it("does not show the export button to viewers", async () => {
    renderProjectPage("viewer");

    expect(await screen.findByRole("heading", { name: "Launch project" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "export to Airtable" })).not.toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalledWith("/api/projects/project-1/export", expect.anything());
  });
});
