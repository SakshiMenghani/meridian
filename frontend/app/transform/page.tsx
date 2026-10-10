import { PageHeader } from "@/components/page-header";
import { UploadPanel } from "@/components/upload-panel";

export default function TransformPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Files"
        title="Transform"
        description="Upload a CSV or Excel file, clean it, then approve a save to the cleaned spreadsheet, Imported PostgreSQL, or Imported MongoDB. After that you can ask questions about those rows."
      />
      <UploadPanel />
    </div>
  );
}
