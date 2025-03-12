#!/bin/bash
# E-Ink Helper Script
# This script provides an easy way to run the E-Ink diagnostic and fix scripts

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Header
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}     E-Ink Display Helper Tool      ${NC}"
echo -e "${BLUE}=====================================${NC}"

# Move to the script directory
cd "$(dirname "$0")"

# Check if we're on a Raspberry Pi
IS_PI=false
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model)
    if [[ $PI_MODEL == *"Raspberry Pi"* ]]; then
        IS_PI=true
        echo -e "${GREEN}Detected: $PI_MODEL${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: Not running on a Raspberry Pi${NC}"
    echo "Some functions may not work correctly."
fi

# Check if we're running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}NOTE: You are not running as root${NC}"
    echo "Some options require root privileges. Consider running with sudo."
fi

# Function to show the menu
show_menu() {
    echo
    echo -e "${BLUE}Options:${NC}"
    echo "1. Run E-Ink diagnostic (no root required)"
    echo "2. Test E-Ink display (no root required)"
    echo "3. Fix E-Ink dependencies (requires root)"
    echo "4. View log files"
    echo "5. Exit"
    echo
    echo -n "Enter your choice [1-5]: "
}

# Function to run the diagnostic script
run_diagnostic() {
    echo -e "\n${BLUE}Running E-Ink diagnostic...${NC}"
    # Execute in python environment if available
    if [ -d "../venv/bin" ]; then
        ../venv/bin/python diagnose_eink.py
    elif [ -d "../.venv/bin" ]; then
        ../.venv/bin/python diagnose_eink.py
    else
        # Try to use system python
        python3 diagnose_eink.py
    fi
}

# Function to run the test script
run_test() {
    echo -e "\n${BLUE}Running E-Ink display test...${NC}"
    if [ -d "../venv/bin" ]; then
        ../venv/bin/python eink_quick_test.py
    elif [ -d "../.venv/bin" ]; then
        ../.venv/bin/python eink_quick_test.py
    else
        python3 eink_quick_test.py
    fi
}

# Function to run the fix script
run_fix() {
    echo -e "\n${BLUE}Fixing E-Ink dependencies...${NC}"
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}This operation requires root privileges.${NC}"
        echo "Please run with sudo:"
        echo -e "${YELLOW}sudo $0${NC}"
        return 1
    fi
    
    if [ -f "fix_eink_dependencies.sh" ]; then
        bash ./fix_eink_dependencies.sh
    else
        echo -e "${RED}Error: fix_eink_dependencies.sh not found${NC}"
        return 1
    fi
}

# Function to view logs
view_logs() {
    echo -e "\n${BLUE}E-Ink related logs:${NC}"
    
    # Check for diagnostic logs
    LOG_FILES=()
    
    # Check for test output log
    if [ -f "eink_test_output.log" ]; then
        LOG_FILES+=("eink_test_output.log")
    fi
    
    # Check for debug logs
    for log in eink_debug_*.log; do
        if [ -f "$log" ]; then
            LOG_FILES+=("$log")
        fi
    done
    
    # Check system journal for E-Ink related messages
    if command -v journalctl &> /dev/null; then
        LOG_FILES+=("System journal (E-Ink related)")
    fi
    
    if [ ${#LOG_FILES[@]} -eq 0 ]; then
        echo -e "${YELLOW}No log files found${NC}"
        return 0
    fi
    
    echo "Available log files:"
    for i in "${!LOG_FILES[@]}"; do
        echo "$((i+1)). ${LOG_FILES[$i]}"
    done
    
    echo
    echo -n "Enter log number to view [1-${#LOG_FILES[@]}] or 0 to cancel: "
    read -r log_choice
    
    if [[ $log_choice -eq 0 ]]; then
        return 0
    fi
    
    if [[ $log_choice -le ${#LOG_FILES[@]} ]]; then
        LOG_IDX=$((log_choice-1))
        
        if [[ "${LOG_FILES[$LOG_IDX]}" == "System journal (E-Ink related)" ]]; then
            echo -e "\n${BLUE}Showing E-Ink related messages from system journal:${NC}"
            journalctl | grep -i "eink\|spi\|gpio" | tail -n 50
            echo -e "\n${YELLOW}Press Enter to continue...${NC}"
            read -r
        else
            LOG_FILE="${LOG_FILES[$LOG_IDX]}"
            echo -e "\n${BLUE}Contents of $LOG_FILE:${NC}"
            if command -v less &> /dev/null; then
                less "$LOG_FILE"
            else
                cat "$LOG_FILE"
                echo -e "\n${YELLOW}Press Enter to continue...${NC}"
                read -r
            fi
        fi
    else
        echo -e "${RED}Invalid selection${NC}"
    fi
}

# Main loop
while true; do
    show_menu
    read -r choice
    
    case $choice in
        1)
            run_diagnostic
            ;;
        2)
            run_test
            ;;
        3)
            run_fix
            ;;
        4)
            view_logs
            ;;
        5)
            echo -e "\n${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "\n${RED}Invalid option. Please try again.${NC}"
            ;;
    esac
done 