#!/bin/bash
# Copyright 2026 The Tendril Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
