#!/bin/bash
# Nutanix CVM health check — verifies ncli/acli availability and cluster access.
export PATH=$PATH:/usr/local/nutanix/bin:/home/nutanix/prism/cli

echo "Nutanix CVM Health Check"
echo "=================================================="
passed=0
failed=0

run_check() {
    local label="$1"
    shift
    if output=$("$@" 2>&1); then
        echo "  PASS: $label"
        ((passed++))
        return 0
    else
        echo "  FAIL: $label ($output)"
        ((failed++))
        return 1
    fi
}

run_check "ncli available" which ncli
run_check "acli available" which acli
run_check "Cluster status" ncli cluster get-params
run_check "Storage pools" ncli storagepool list
run_check "VM list" acli vm.list

echo ""
echo "Results: $passed passed, $failed failed, $((passed + failed)) total"
[ "$failed" -eq 0 ] && exit 0 || exit 1
