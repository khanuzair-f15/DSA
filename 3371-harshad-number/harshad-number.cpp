class Solution {
public:
    int sumOfTheDigitsOfHarshadNumber(int x) {
        long long sum = 0;
        int temp = x;
        // 18
        if (x == 0) {
            return -1;
        }
        while (temp != 0) {
            int digit = temp % 10;
            sum += digit;
            temp /= 10;
        }
 
        if (x % sum == 0) {
            return sum;
        }
        return -1;
    }
};