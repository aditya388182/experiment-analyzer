import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MappingForm } from "../src/components/MappingForm";

const columns = ["user", "group", "converted", "revenue", "prior"];
const preview = [
  ["1", "control", "0", "0", "3.5"],
  ["2", "treatment", "1", "12.5", "1.0"],
  ["3", "control", "1", "7", "2.0"],
];

function setup() {
  const onSubmit = vi.fn();
  render(<MappingForm columns={columns} preview={preview} onSubmit={onSubmit} />);
  return { onSubmit, user: userEvent.setup() };
}

describe("mapping form", () => {
  it("guesses the variant column and control label from the preview", () => {
    setup();
    expect(screen.getByLabelText("Variant column")).toHaveValue("group");
    expect(screen.getByLabelText("Control label")).toHaveValue("control");
    expect(screen.getByText(/Values seen in the preview: control, treatment/)).toBeInTheDocument();
  });

  it("requires a metric column", async () => {
    const { onSubmit, user } = setup();
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    expect(await screen.findByText("Pick the outcome (metric) column.")).toBeInTheDocument();
    expect(screen.getByLabelText("Metric column")).toHaveAttribute("aria-invalid", "true");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a metric column equal to the variant column", async () => {
    const { onSubmit, user } = setup();
    await user.selectOptions(screen.getByLabelText("Metric column"), "group");
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    expect(await screen.findByText("The metric column must differ from the variant column.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a planned split that does not sum to 1 and an alpha above 0.2", async () => {
    const { onSubmit, user } = setup();
    await user.selectOptions(screen.getByLabelText("Metric column"), "converted");
    await user.type(screen.getByLabelText("Planned split (optional)"), "0.5, 0.6");
    await user.clear(screen.getByLabelText("Significance level (alpha)"));
    await user.type(screen.getByLabelText("Significance level (alpha)"), "0.5");
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    expect(await screen.findByText("The shares must add up to 1.")).toBeInTheDocument();
    expect(screen.getByText("Alpha must be at most 0.2.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("suggests continuous for a non-0/1 metric and submits a clean mapping", async () => {
    const { onSubmit, user } = setup();
    await user.selectOptions(screen.getByLabelText("Metric column"), "revenue");
    expect(screen.getByLabelText(/Continuous/)).toBeChecked();
    await user.selectOptions(screen.getByLabelText("Pre-period column (optional)"), "prior");
    await user.type(screen.getByLabelText("Planned split (optional)"), "0.5,0.5");
    expect(screen.getByText(/in this order: control, treatment/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    expect(onSubmit).toHaveBeenCalledWith({
      variant_col: "group",
      control_label: "control",
      metric_col: "revenue",
      metric_type: "continuous",
      pre_period_col: "prior",
      planned_split: [0.5, 0.5],
      alpha: 0.05,
    });
  });

  it("does not guess a type from an all-zero preview column", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<MappingForm columns={["g", "spend"]} preview={[["control", "0"], ["b", "0"]]} onSubmit={onSubmit} />);
    await user.click(screen.getByLabelText(/Continuous/));
    await user.selectOptions(screen.getByLabelText("Metric column"), "spend");
    expect(screen.getByLabelText(/Continuous/)).toBeChecked();
  });

  it("suggests binary for a 0/1 metric and sends null for empty optional fields", async () => {
    const { onSubmit, user } = setup();
    await user.selectOptions(screen.getByLabelText("Metric column"), "converted");
    expect(screen.getByLabelText(/Binary/)).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Analyze" }));
    expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ metric_type: "binary", pre_period_col: null, planned_split: null }));
  });
});
