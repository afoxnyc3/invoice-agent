#!/bin/bash
# Wait for GitHub Actions deployment to complete

echo "⏳ Monitoring deployment progress..."
echo "====================================="
echo ""

FUNC_NAME="func-invoice-agent-dev"
RG_NAME="rg-invoice-agent-dev"

# Get initial package URL
INITIAL_PKG=$(az functionapp config appsettings list --name "$FUNC_NAME" --resource-group "$RG_NAME" --query "[?name=='WEBSITE_RUN_FROM_PACKAGE'].value" -o tsv)
echo "📦 Current package: $(basename "$INITIAL_PKG")"
echo ""

MAX_WAIT=600  # 10 minutes
ELAPSED=0
INTERVAL=15

while [ $ELAPSED -lt $MAX_WAIT ]; do
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))

    CURRENT_PKG=$(az functionapp config appsettings list --name "$FUNC_NAME" --resource-group "$RG_NAME" --query "[?name=='WEBSITE_RUN_FROM_PACKAGE'].value" -o tsv 2>/dev/null)

    if [ "$CURRENT_PKG" != "$INITIAL_PKG" ]; then
        echo ""
        echo "✅ New deployment detected!"
        echo "📦 New package: $(basename "$CURRENT_PKG")"
        echo ""
        echo "Waiting 30s for Function App to fully start..."
        sleep 30

        echo "Checking if MailIngest function is deployed..."
        az functionapp function show --name "$FUNC_NAME" --resource-group "$RG_NAME" --function-name MailIngest --query "name" -o tsv 2>/dev/null

        if [ $? -eq 0 ]; then
            echo "✅ MailIngest function successfully deployed!"

            # Calculate next timer run
            CURRENT_MIN=$(date +%M | sed 's/^0//')
            NEXT_RUN=$((((CURRENT_MIN / 5) + 1) * 5))
            if [ $NEXT_RUN -ge 60 ]; then
                NEXT_RUN=$((NEXT_RUN - 60))
            fi

            echo ""
            echo "⏰ Next email poll: :$(printf %02d $NEXT_RUN)"
            echo "📧 4 test emails waiting to be processed"
            exit 0
        else
            echo "⚠️  MailIngest function not found yet, waiting..."
        fi
    else
        printf "."
    fi
done

echo ""
echo "⚠️  Deployment did not complete within $((MAX_WAIT/60)) minutes"
echo "   Check GitHub Actions: https://github.com/afoxnyc3/invoice-agent/actions"
