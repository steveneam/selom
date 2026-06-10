"use client";

import { useParams } from "next/navigation";
import { ProjectWorkspace } from "@/components/project/project-workspace";

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  return <ProjectWorkspace projectId={params.id} />;
}
