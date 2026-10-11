import Link from "next/link";
import { PageHeader } from "@/components/page-header";
import { UploadPanel } from "@/components/upload-panel";

export default function TransformPage() {
  return (
    <div>
      <Link href="/sources/new" className="text-sm font-semibold text-tide">
        ← Add a source
      </Link>
      <div className="mt-4">
        <PageHeader
          eyebrow="Your data"
          title="Upload a file"
          description="Add a CSV or Excel file. Meridian checks every column, lets you fix names and types, and then saves a clean copy you can ask questions about."
        />
      </div>
      <UploadPanel />
    </div>
  );
}
