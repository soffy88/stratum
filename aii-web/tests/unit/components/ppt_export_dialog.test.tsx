import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PptExportDialog } from "@/components/ppt/PptExportDialog";
import * as ppt from "@/lib/ppt-export";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("@/lib/ppt-export", async () => {
  const actual = await vi.importActual<typeof import("@/lib/ppt-export")>("@/lib/ppt-export");
  return {
    ...actual,
    getPptStyles: vi.fn(),
    getPptBookChapters: vi.fn(),
    listPptExports: vi.fn(),
    createPptExport: vi.fn(),
    getPptExport: vi.fn(),
    fetchPptBlob: vi.fn(),
    downloadPptExport: vi.fn(),
  };
});

const STYLES = {
  styles: [
    { id: "paper-notes", name: "纸感手记", scheme: "light", mood: "warm", best_for: "读书笔记", avoid_for: "" },
    { id: "dark-tech", name: "深色科技", scheme: "dark", mood: "dark", best_for: "AI 与科技", avoid_for: "" },
  ],
  default: "paper-notes",
  pages: { min: 5, max: 30, default: 12 },
};

const JOB = {
  job_id: "job1",
  substrate_id: "sub1",
  run_id: null,
  chapter_id: "ch2",
  style: "dark-tech",
  pages: 9,
  status: "queued",
  stage: "queued",
  progress: 0,
  title: null,
  language: null,
  slide_count: null,
  file_size: null,
  qa: {},
  error: null,
  created_at: "",
  finished_at: null,
  download_url: null,
  preview_urls: [],
};

describe("PptExportDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(ppt.getPptStyles).mockResolvedValue(STYLES);
    vi.mocked(ppt.getPptBookChapters).mockResolvedValue({
      substrate_id: "sub1",
      ready: true,
      chapters: [
        { chapter_id: "ch1", title: "Chapter 1: 函数与极限", question: "" },
        { chapter_id: "ch2", title: "Chapter 2: 导数与微分", question: "" },
      ],
    });
    vi.mocked(ppt.listPptExports).mockResolvedValue([]);
    vi.mocked(ppt.createPptExport).mockResolvedValue(JOB as ppt.PptExportJob);
  });

  it("lists the style presets by Chinese name and the book's chapters", async () => {
    render(<PptExportDialog open onClose={() => {}} substrateId="sub1" bookTitle="高等数学" />);
    expect(await screen.findByRole("radio", { name: /纸感手记/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /深色科技/ })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("option", { name: "Chapter 2: 导数与微分" })).toBeInTheDocument());
    expect(screen.getByRole("radio", { name: /纸感手记/ })).toHaveAttribute("aria-checked", "true");
  });

  it("submits the chosen scope, style and page count, then shows progress", async () => {
    render(<PptExportDialog open onClose={() => {}} substrateId="sub1" />);
    fireEvent.click(await screen.findByRole("radio", { name: /深色科技/ }));
    await screen.findByRole("option", { name: "Chapter 2: 导数与微分" });
    fireEvent.change(screen.getByLabelText("范围"), { target: { value: "ch2" } });
    fireEvent.change(screen.getByLabelText("页数"), { target: { value: "9" } });
    fireEvent.click(screen.getByRole("button", { name: "生成 PPT" }));
    await waitFor(() =>
      expect(ppt.createPptExport).toHaveBeenCalledWith(
        expect.objectContaining({ substrate_id: "sub1", chapter_id: "ch2", style: "dark-tech", pages: 9 }),
      ),
    );
    expect(await screen.findByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText("排队中")).toBeInTheDocument();
  });

  it("uses the run id when opened from a chapter page", async () => {
    render(<PptExportDialog open onClose={() => {}} runId="br_1" chapterId="ch3" />);
    await screen.findByRole("radio", { name: /纸感手记/ });
    expect(screen.getByLabelText("范围")).toHaveValue("ch3");
    fireEvent.click(screen.getByRole("button", { name: "生成 PPT" }));
    await waitFor(() =>
      expect(ppt.createPptExport).toHaveBeenCalledWith(
        expect.objectContaining({ run_id: "br_1", chapter_id: "ch3", substrate_id: undefined }),
      ),
    );
    expect(ppt.getPptBookChapters).not.toHaveBeenCalled();
  });
});
