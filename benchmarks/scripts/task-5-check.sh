#!/bin/bash
# Task 5 Check: Verify bug is fixed and routing still works
cd /Users/jacobbrizinski/Projects/kitty

# Verify the file still loads and routing works
output=$(python3 -c "
from src.core.domain_router import DomainRouter
r = DomainRouter()
result = r.route('fix my guitar amp')
print('domain:', result.domain)
print('confidence:', result.confidence)
print('specialist:', result.specialist)
" 2>&1)

if [ $? -ne 0 ]; then
    echo "FAIL: DomainRouter failed: $output"
    exit 1
fi

# Verify specialist is always a string (the original bug)
if python3 -c "
from src.core.domain_router import DomainRouter, RoutingDecision, Domain
# Test all domains route successfully
r = DomainRouter()
for d in list(Domain):
    result = r.get_routing_for_domain(d)
    assert isinstance(result.specialist, str), f'specialist is not str: {result.specialist}'
print('All domains route correctly')
" 2>&1; then
    echo "PASS: All domains route with string specialists"
    exit 0
else
    echo "FAIL: Type issue persists"
    exit 1
fi
