class Solution {
public:
    bool checkPerfectNumber(int n) {

        int sum = 0;

        for (int i = 1; i < n; i++) {
            if (n % i == 0) {
                sum =sum+ i;
            }
        }
        
        cout<<sum;
        if (sum == n) {
            return true;
        }
        return false;
    }
};