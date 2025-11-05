import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ViewParamsFormProps {
  schema: any;
  params: Record<string, any>;
  onChange: (params: Record<string, any>) => void;
}

export function ViewParamsForm({ schema, params, onChange }: ViewParamsFormProps) {
  if (!schema || !schema.properties) {
    return <div className="text-sm text-muted-foreground">No parameters required</div>;
  }

  const handleChange = (key: string, value: any) => {
    onChange({ ...params, [key]: value });
  };

  const renderField = (key: string, property: any) => {
    const label = property.title || key;
    const value = params[key] || "";

    // Handle enum fields (select dropdowns)
    if (property.enum) {
      return (
        <div key={key} className="space-y-2">
          <Label htmlFor={key}>{label}</Label>
          <Select
            value={value}
            onValueChange={(val) => handleChange(key, val)}
          >
            <SelectTrigger id={key}>
              <SelectValue placeholder={`Select ${label}`} />
            </SelectTrigger>
            <SelectContent>
              {property.enum.map((option: string) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      );
    }

    // Handle integer fields
    if (property.type === "integer") {
      return (
        <div key={key} className="space-y-2">
          <Label htmlFor={key}>{label}</Label>
          <Input
            id={key}
            type="number"
            value={value}
            onChange={(e) => handleChange(key, parseInt(e.target.value) || 0)}
            placeholder={property.description || `Enter ${label}`}
          />
        </div>
      );
    }

    // Default to string/text input
    return (
      <div key={key} className="space-y-2">
        <Label htmlFor={key}>{label}</Label>
        <Input
          id={key}
          type="text"
          value={value}
          onChange={(e) => handleChange(key, e.target.value)}
          placeholder={property.description || `Enter ${label}`}
        />
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {Object.entries(schema.properties).map(([key, property]) =>
        renderField(key, property)
      )}
    </div>
  );
}
