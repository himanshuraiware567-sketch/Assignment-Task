import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TaskDetail } from "@/components/TaskDetail";
import { apiFetch, getStoredUser } from "@/lib/api-client";
import type { ApiProjectMember, ApiTask, Role } from "@/types";

vi.mock("@/lib/api-client", () => ({
  apiFetch: vi.fn(),
  getStoredUser: vi.fn(),
}));

const mockedApiFetch = apiFetch as unknown as {
  mockResolvedValue: (value: unknown) => void;
  mockImplementation: (
    implementation: (path: string, options?: RequestInit) => Promise<unknown>,
  ) => void;
};

const currentUser = {
  id: "user-1",
  name: "Alex Member",
  email: "alex@example.com",
};

const task: ApiTask = {
  id: "task-1",
  projectId: "project-1",
  title: "Example task",
  description: null,
  status: "todo",
  assigneeId: null,
  createdById: currentUser.id,
  position: 0,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

const existingComment = {
  id: "comment-1",
  content: "Please check the acceptance criteria.",
  author: currentUser,
  createdAt: "2026-01-01T01:00:00Z",
};

function renderTaskDetail(role: Role) {
  const member: ApiProjectMember = {
    id: "membership-1",
    role,
    user: currentUser,
  };
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <TaskDetail task={task} projectId="project-1" members={[member]} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe("TaskDetail comments", () => {
  beforeEach(() => {
    vi.mocked(getStoredUser).mockReturnValue(currentUser);
    mockedApiFetch.mockResolvedValue({ comments: [existingComment] });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads and displays comments for the task", async () => {
    renderTaskDetail("member");

    expect(await screen.findByText(existingComment.content)).toBeInTheDocument();
    const comments = within(screen.getByRole("heading", { name: "comments" }).closest("section")!);
    expect(comments.getByText(currentUser.name)).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/api/tasks/task-1/comments");
  });

  it("lets a member submit a comment", async () => {
    mockedApiFetch.mockImplementation(async (_path, options) => {
      if (options?.method === "POST") {
        return { comment: { ...existingComment, id: "comment-2", content: "New comment" } };
      }
      return { comments: [existingComment] };
    });

    renderTaskDetail("member");
    const input = await screen.findByRole("textbox", { name: "Write a comment" });
    fireEvent.change(input, { target: { value: "New comment" } });
    fireEvent.click(screen.getByRole("button", { name: "comment" }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith("/api/tasks/task-1/comments", {
        method: "POST",
        body: JSON.stringify({ content: "New comment" }),
      });
    });
    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("shows comments to viewers without a comment form", async () => {
    renderTaskDetail("viewer");

    expect(await screen.findByText(existingComment.content)).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Write a comment" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "comment" })).not.toBeInTheDocument();
  });
});
