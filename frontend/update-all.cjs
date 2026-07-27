const fs = require('fs');

const imageUploadComp = `
function ImageUpload({ imagePreview, onImageSelect, onImageRemove, disabled }: { imagePreview: string | null; onImageSelect: (file: string) => void; onImageRemove: () => void; disabled?: boolean }) {
  const handleDrop = (e: React.DragEvent) => {
    if (disabled) return;
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith('image/')) handleFile(file);
  };
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    const file = e.target.files?.[0];
    if (file && file.type.startsWith('image/')) handleFile(file);
  };
  const handleFile = (file: File) => {
    // We import toast from 'sonner' in these files
    if (file.size > 5 * 1024 * 1024) { 
        alert('Image must be under 5MB'); 
        return; 
    }
    const reader = new FileReader();
    reader.onload = (e) => onImageSelect(e.target?.result as string);
    reader.readAsDataURL(file);
  };

  return (
    <div 
      onDragOver={e => e.preventDefault()} 
      onDrop={handleDrop}
      className={\`relative h-[160px] w-full rounded-lg border-2 border-dashed border-muted-foreground/30 bg-muted/20 hover:bg-muted/40 transition-colors flex items-center justify-center overflow-hidden \${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}\`}
      onClick={() => !disabled && document.getElementById('img-upload-input')?.click()}
    >
      <input id="img-upload-input" type="file" accept="image/jpeg, image/png, image/gif" className="hidden" onChange={handleChange} disabled={disabled} />
      {imagePreview ? (
        <>
          <img src={imagePreview} alt="Preview" className="w-full h-full object-cover" />
          {!disabled && (
            <button type="button" onClick={(e) => { e.stopPropagation(); onImageRemove(); }} className="absolute top-2 right-2 bg-black/50 hover:bg-black/70 text-white rounded-full p-1">
              <X className="w-4 h-4" />
            </button>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center text-muted-foreground pointer-events-none">
          <Upload className="w-8 h-8 mb-2 opacity-50" />
          <span className="text-sm">Drag & drop image here or click to upload</span>
          <span className="text-xs opacity-70">JPG, PNG, GIF up to 5MB</span>
        </div>
      )}
    </div>
  );
}
`;

function processServices() {
  const path = 'f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/services.tsx';
  let content = fs.readFileSync(path, 'utf8');

  content = content.replace(
    "import { Plus, Search, Edit, Trash2, GripVertical } from 'lucide-react';",
    "import { Plus, Search, Edit, Trash2, GripVertical, Upload, X, Eye, EyeOff, Circle, ImageIcon } from 'lucide-react';"
  );
  content = content.replace(
    "import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';",
    "import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';\nimport { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';"
  );
  content = content.replace(
    "  requirements: Array<{ resource_type: string; quantity: number }>;\n}",
    "  requirements: Array<{ resource_type: string; quantity: number }>;\n  image: string | null;\n}"
  );
  content = content.replace(
    "export default function ServicesPage() {",
    imageUploadComp + "\nexport default function ServicesPage() {"
  );
  content = content.replace(
    "    requirements: []\n  };",
    "    requirements: [],\n    image: null\n  };"
  );
  content = content.replace(
    "      requirements: svc.requirements || []\n    });",
    "      requirements: svc.requirements || [],\n      image: svc.image || null\n    });"
  );
  content = content.replace(
    '<div className="flex h-full w-full gap-4">',
    '<TooltipProvider>\n    <div className="flex h-full w-full gap-4">'
  );
  const lastDivIndex = content.lastIndexOf('</div>');
  content = content.substring(0, lastDivIndex) + '</div>\n    </TooltipProvider>' + content.substring(lastDivIndex + 6);

  content = content.replace(
    /<div className="flex justify-between items-start">[\s\S]*?<div className="text-xs text-muted-foreground mt-2">\$\{svc\.price\} &bull; \{svc\.duration\} mins<\/div>\n                      <\/div>/g,
    `<div className="flex justify-between items-start">
                          <div className="flex gap-3 items-start">
                            <GripVertical className="w-4 h-4 text-muted-foreground opacity-50 hover:opacity-100 cursor-grab mt-2 shrink-0" onClick={e => e.stopPropagation()} />
                            {svc.image ? (
                              <img src={svc.image} alt={svc.name} className="w-[80px] h-[80px] object-cover rounded-md shrink-0" />
                            ) : (
                              <div className="w-[80px] h-[80px] bg-muted rounded-md flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-6 h-6 opacity-20"/></div>
                            )}
                            <div className="flex flex-col gap-1 mt-1">
                              <span className="font-medium leading-none">{svc.name}</span>
                              <span className="text-xs text-muted-foreground line-clamp-2">{svc.description}</span>
                              <div className="text-xs text-muted-foreground mt-1">\${svc.price} &bull; {svc.duration} mins</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button onClick={() => updateServiceQuick(svc.id, { is_visible: !svc.is_visible })} className="p-2 hover:bg-muted rounded-full">
                                  {svc.is_visible ? <Eye className="w-4 h-4 text-emerald-500" /> : <EyeOff className="w-4 h-4 text-muted-foreground/40" />}
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>{svc.is_visible ? 'Visible on booking page' : 'Hidden from booking page'}</TooltipContent>
                            </Tooltip>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <button onClick={() => updateServiceQuick(svc.id, { active: !svc.active })} className="p-2 hover:bg-muted rounded-full">
                                  <Circle className={\`w-4 h-4 \${svc.active ? 'fill-emerald-500 text-emerald-500' : 'text-muted-foreground/40'}\`} />
                                </button>
                              </TooltipTrigger>
                              <TooltipContent>{svc.active ? 'Active' : 'Inactive'}</TooltipContent>
                            </Tooltip>
                          </div>
                        </div>
                      </div>`
  );

  content = content.replace(
    `                      <Label htmlFor="description">Description</Label>`,
    `                      <Label>Image</Label>
                      <ImageUpload 
                        imagePreview={formData.image} 
                        onImageSelect={(file) => setFormData({ ...formData, image: file })} 
                        onImageRemove={() => setFormData({ ...formData, image: null })} 
                        disabled={!isEditing} 
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="description">Description</Label>`
  );

  content = content.replace(
    /<div className="grid grid-cols-3 gap-4">[\s\S]*?max_advance_days[\s\S]*?<\/div>\s*<\/div>\s*<\/AccordionContent>/,
    `<div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="duration">Duration (mins)</Label>
                        <Input 
                          id="duration" 
                          type="number"
                          value={formData.duration} 
                          onChange={(e) => setFormData({ ...formData, duration: parseInt(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="buffer_before">Buffer Before (mins)</Label>
                        <Input 
                          id="buffer_before" 
                          type="number"
                          value={formData.buffer_before} 
                          onChange={(e) => setFormData({ ...formData, buffer_before: parseInt(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="buffer_after">Buffer After (mins)</Label>
                        <Input 
                          id="buffer_after" 
                          type="number"
                          value={formData.buffer_after} 
                          onChange={(e) => setFormData({ ...formData, buffer_after: parseInt(e.target.value) || 0 })}
                          disabled={!isEditing}
                        />
                      </div>
                    </div>
                  </AccordionContent>`
  );

  fs.writeFileSync(path, content, 'utf8');
}

function processAddOns() {
  const path = 'f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/add-ons.tsx';
  let content = fs.readFileSync(path, 'utf8');

  content = content.replace(
    "import { Plus, Search, Trash2, Edit } from 'lucide-react';",
    "import { Plus, Search, Trash2, Edit, Upload, X, Eye, EyeOff, Circle, ImageIcon } from 'lucide-react';"
  );
  content = content.replace(
    "import { toast } from 'sonner';",
    "import { toast } from 'sonner';\nimport { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';"
  );
  content = content.replace(
    "  service_ids?: string[];\n}",
    "  service_ids?: string[];\n  image?: string | null;\n}"
  );
  content = content.replace(
    "export default function AddOnsPage() {",
    imageUploadComp + "\nexport default function AddOnsPage() {"
  );
  content = content.replace(
    "      active: true,\n      service_ids: [],\n    });",
    "      active: true,\n      service_ids: [],\n      image: null,\n    });"
  );
  content = content.replace(
    "      service_ids: addon.service_ids || [],\n    });",
    "      service_ids: addon.service_ids || [],\n      image: addon.image || null,\n    });"
  );
  
  content = content.replace(
    '<div className="flex h-[calc(100vh-65px)]">',
    '<TooltipProvider>\n    <div className="flex h-[calc(100vh-65px)]">'
  );
  const lastDivIndex = content.lastIndexOf('</div>');
  content = content.substring(0, lastDivIndex) + '</div>\n    </TooltipProvider>' + content.substring(lastDivIndex + 6);

  // Quick active toggle
  if (!content.includes('updateAddonQuick')) {
    content = content.replace(
      "  const handleDelete = async (id: string) => {",
      `  const updateAddonQuick = async (id: string, updates: Partial<AddOn>) => {
    try {
      setAddOns(prev => prev.map(a => a.id === id ? { ...a, ...updates } : a));
      await apiClient.put(\`/api/admin/add-ons/\${id}\`, updates);
      toast.success('Add-on updated');
    } catch {
      toast.error('Failed to update add-on');
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {`
    );
  }

  content = content.replace(
    /<div[\s\S]*?key=\{addon\.id\}[\s\S]*?className={`flex items-center justify-between p-3 rounded-md cursor-pointer transition-colors \${[\s\S]*?onClick=\{\(\) => handleSelect\(addon\)\}[\s\S]*?>\s*<div>[\s\S]*?<div className="font-medium">\{addon\.name\}<\/div>[\s\S]*?<div className="text-xs text-muted-foreground flex gap-2 mt-1">[\s\S]*?<span>\$\{addon\.price\}<\/span>[\s\S]*?<span>•<\/span>[\s\S]*?<span>\{addon\.duration\} mins<\/span>[\s\S]*?<\/div>[\s\S]*?<\/div>[\s\S]*?<Badge variant=\{addon\.active \? 'default' : 'secondary'\}>[\s\S]*?\{addon\.active \? 'Active' : 'Inactive'\}[\s\S]*?<\/Badge>[\s\S]*?<\/div>/g,
    `<div
                  key={addon.id}
                  className={\`flex items-start justify-between p-3 rounded-md cursor-pointer transition-colors \${
                    selectedId === addon.id
                      ? 'bg-primary/10 text-primary border-primary'
                      : 'border border-transparent hover:bg-muted/50'
                  }\`}
                  onClick={() => handleSelect(addon)}
                >
                  <div className="flex gap-3 items-start">
                    {addon.image ? (
                      <img src={addon.image} alt={addon.name} className="w-[80px] h-[80px] object-cover rounded-md shrink-0" />
                    ) : (
                      <div className="w-[80px] h-[80px] bg-muted rounded-md flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-6 h-6 opacity-20"/></div>
                    )}
                    <div className="flex flex-col gap-1 mt-1">
                      <span className="font-medium leading-none">{addon.name}</span>
                      <span className="text-xs text-muted-foreground line-clamp-2">{addon.description}</span>
                      <div className="text-xs text-muted-foreground mt-1">\${addon.price} &bull; {addon.duration} mins</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button onClick={() => updateAddonQuick(addon.id, { active: !addon.active })} className="p-2 hover:bg-muted rounded-full">
                          <Circle className={\`w-4 h-4 \${addon.active ? 'fill-emerald-500 text-emerald-500' : 'text-muted-foreground/40'}\`} />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>{addon.active ? 'Active' : 'Inactive'}</TooltipContent>
                    </Tooltip>
                  </div>
                </div>`
  );

  content = content.replace(
    `<Label>Name</Label>`,
    `<Label>Image</Label>
                  <ImageUpload 
                    imagePreview={formData.image || null} 
                    onImageSelect={(file) => setFormData({ ...formData, image: file })} 
                    onImageRemove={() => setFormData({ ...formData, image: null })} 
                    disabled={!isEditing} 
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Name</Label>`
  );

  fs.writeFileSync(path, content, 'utf8');
}

function processProducts() {
  const path = 'f:/Projects/fastapi_bookings/frontend/src/pages/admin/catalog/products.tsx';
  let content = fs.readFileSync(path, 'utf8');

  content = content.replace(
    "import { Plus, Search, Trash2, Edit } from 'lucide-react';",
    "import { Plus, Search, Trash2, Edit, Upload, X, Eye, EyeOff, Circle, ImageIcon } from 'lucide-react';"
  );
  content = content.replace(
    "import { toast } from 'sonner';",
    "import { toast } from 'sonner';\nimport { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';"
  );
  content = content.replace(
    "  location_ids?: string[];\n}",
    "  location_ids?: string[];\n  image?: string | null;\n}"
  );
  content = content.replace(
    "export default function ProductsPage() {",
    imageUploadComp + "\nexport default function ProductsPage() {"
  );
  content = content.replace(
    "      location_ids: [],\n    });",
    "      location_ids: [],\n      image: null,\n    });"
  );
  content = content.replace(
    "      location_ids: product.location_ids || [],\n    });",
    "      location_ids: product.location_ids || [],\n      image: product.image || null,\n    });"
  );

  content = content.replace(
    '<div className="flex h-[calc(100vh-65px)]">',
    '<TooltipProvider>\n    <div className="flex h-[calc(100vh-65px)]">'
  );
  const lastDivIndex = content.lastIndexOf('</div>');
  content = content.substring(0, lastDivIndex) + '</div>\n    </TooltipProvider>' + content.substring(lastDivIndex + 6);

  if (!content.includes('updateProductQuick')) {
    content = content.replace(
      "  const handleDelete = async (id: string) => {",
      `  const updateProductQuick = async (id: string, updates: Partial<Product>) => {
    try {
      setProducts(prev => prev.map(p => p.id === id ? { ...p, ...updates } : p));
      await apiClient.put(\`/api/admin/products/\${id}\`, updates);
      toast.success('Product updated');
    } catch {
      toast.error('Failed to update product');
      fetchData();
    }
  };

  const handleDelete = async (id: string) => {`
    );
  }

  content = content.replace(
    /<div[\s\S]*?key=\{product\.id\}[\s\S]*?className={`flex items-center justify-between p-3 rounded-md cursor-pointer transition-colors \${[\s\S]*?onClick=\{\(\) => handleSelect\(product\)\}[\s\S]*?>\s*<div>[\s\S]*?<div className="font-medium">\{product\.name\}<\/div>[\s\S]*?<div className="text-xs text-muted-foreground flex gap-2 mt-1">[\s\S]*?<span>\{product\.sku \|\| 'No SKU'\}<\/span>[\s\S]*?<span>•<\/span>[\s\S]*?<span>\$\{product\.price\}<\/span>[\s\S]*?<\/div>[\s\S]*?<\/div>[\s\S]*?<Badge variant=\{product\.active \? 'default' : 'secondary'\}>[\s\S]*?\{product\.active \? 'Active' : 'Inactive'\}[\s\S]*?<\/Badge>[\s\S]*?<\/div>/g,
    `<div
                  key={product.id}
                  className={\`flex items-start justify-between p-3 rounded-md cursor-pointer transition-colors \${
                    selectedId === product.id
                      ? 'bg-primary/10 text-primary border-primary'
                      : 'border border-transparent hover:bg-muted/50'
                  }\`}
                  onClick={() => handleSelect(product)}
                >
                  <div className="flex gap-3 items-start">
                    {product.image ? (
                      <img src={product.image} alt={product.name} className="w-[80px] h-[80px] object-cover rounded-md shrink-0" />
                    ) : (
                      <div className="w-[80px] h-[80px] bg-muted rounded-md flex items-center justify-center text-muted-foreground shrink-0"><ImageIcon className="w-6 h-6 opacity-20"/></div>
                    )}
                    <div className="flex flex-col gap-1 mt-1">
                      <span className="font-medium leading-none">{product.name}</span>
                      <span className="text-xs text-muted-foreground line-clamp-2">{product.description}</span>
                      <div className="text-xs text-muted-foreground mt-1">{product.sku || 'No SKU'} &bull; \${product.price}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button onClick={() => updateProductQuick(product.id, { active: !product.active })} className="p-2 hover:bg-muted rounded-full">
                          <Circle className={\`w-4 h-4 \${product.active ? 'fill-emerald-500 text-emerald-500' : 'text-muted-foreground/40'}\`} />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent>{product.active ? 'Active' : 'Inactive'}</TooltipContent>
                    </Tooltip>
                  </div>
                </div>`
  );

  content = content.replace(
    `<Label>Name</Label>`,
    `<Label>Image</Label>
                  <ImageUpload 
                    imagePreview={formData.image || null} 
                    onImageSelect={(file) => setFormData({ ...formData, image: file })} 
                    onImageRemove={() => setFormData({ ...formData, image: null })} 
                    disabled={!isEditing} 
                  />
                </div>
                <div className="col-span-2 space-y-2">
                  <Label>Name</Label>`
  );

  fs.writeFileSync(path, content, 'utf8');
}

processServices();
processAddOns();
processProducts();
console.log('Done replacing contents.');
