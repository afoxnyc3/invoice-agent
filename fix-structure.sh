#!/bin/bash
# Fix the Azure Functions structure issue

echo "🔧 Restructuring project for Azure Functions..."

# Move functions to the root of src/
echo "📁 Moving functions to src/ root..."
cd src

# Move each function directory from functions/ to src/
for func in functions/*; do
  if [ -d "$func" ]; then
    func_name=$(basename "$func")
    echo "  Moving $func_name..."
    mv "$func" "./$func_name"
  fi
done

# Remove the now-empty functions directory
rmdir functions

# Update imports in the function files to reflect new structure
echo "📝 Updating imports..."
for func in MailIngest ExtractEnrich PostToAP Notify AddVendor; do
  if [ -d "$func" ]; then
    echo "  Updating $func/__init__.py..."
    # Update imports from 'from shared.' to stay the same (already correct)
    # No changes needed as imports are already using 'from shared.'
  fi
done

cd ..

echo "✅ Structure fixed!"
echo ""
echo "New structure:"
tree -L 2 src/ 2>/dev/null || ls -la src/

echo ""
echo "📋 Next steps:"
echo "1. Review the changes"
echo "2. Test locally: cd src && func start"
echo "3. Commit and push to trigger deployment"