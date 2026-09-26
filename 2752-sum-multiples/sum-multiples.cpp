class Solution {
public:
    int sumOfMultiples(int n) {
        unordered_set<int> s;
        long long sum = 0;
        for (int i = 1; i <= n; i++) {
            if (i % 3 == 0 || i % 7 == 0 || i % 5 == 0) {
                sum += i;
            }
        }

        return sum;
    }
};