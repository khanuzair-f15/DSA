class Solution {
public:
    int differenceOfSums(int n, int m) {

        long long num1 = 0;
        long long num2 = 0;

        long long k = n / m;

        num2 = 1LL * m * k * (k + 1) / 2;
        num1 = 1LL * n * (n + 1) / 2 - num2;
        
        return num1 - num2;
    }
};