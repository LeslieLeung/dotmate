import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/api/client";
import { Loader2 } from "lucide-react";

interface PreviewPanelProps {
  viewType: string;
  params: Record<string, any>;
}

export function PreviewPanel({ viewType, params }: PreviewPanelProps) {
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generatePreview = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.generatePreview(viewType, params);
      setPreview(response.image);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate preview");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Preview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Button onClick={generatePreview} disabled={loading} className="w-full">
          {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Generate Preview
        </Button>

        {error && (
          <div className="p-4 text-sm text-red-500 bg-red-50 dark:bg-red-900/10 rounded-md">
            {error}
          </div>
        )}

        {preview && (
          <div className="border rounded-md p-4 bg-gray-50 dark:bg-gray-900">
            <img
              src={preview}
              alt="Preview"
              className="w-full h-auto"
              style={{ imageRendering: "pixelated" }}
            />
          </div>
        )}

        {!preview && !error && !loading && (
          <div className="text-center text-sm text-muted-foreground p-8 border-2 border-dashed rounded-md">
            Click "Generate Preview" to see how this view will look
          </div>
        )}
      </CardContent>
    </Card>
  );
}
