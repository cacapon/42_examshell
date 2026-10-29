#!/bin/bash

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 Running tests for mini_serv${NC}"
echo "=========================================="
echo ""

# Check if user file exists
USER_C="../../../rendu/mini_serv/mini_serv.c"

if [ ! -f "$USER_C" ]; then
    echo -e "${RED}❌ User solution not found: $USER_C${NC}"
    exit 1
fi

# Test 1: Check C compilation and linking
echo -e "${BLUE}📦 Test 1: Checking compilation...${NC}"

gcc -Wall -Wextra -Werror "$USER_C" -o user_mini_serv 2>&1

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Compilation failed!${NC}"
    echo -e "${YELLOW}Please check your C syntax.${NC}"
    rm -f user_mini_serv 2>/dev/null
    exit 1
fi

echo -e "${GREEN}✅ Compilation and linking successful!${NC}"
echo ""

# Cleanup
rm -f user_mini_serv 2>/dev/null

# Final report
echo "=========================================="
echo -e "${GREEN}✅ Build check passed!${NC}"
echo -e "${YELLOW}⚠️ Functional tests are not implemented yet.${NC}"
echo -e "${YELLOW}This does not mean the solution passes the exam.${NC}"
echo ""

exit 0
