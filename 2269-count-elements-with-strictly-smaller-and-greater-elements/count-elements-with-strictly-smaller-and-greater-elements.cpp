class Solution {
public:
    int countElements(vector<int>& nums) {
        int minV = INT_MAX;
        int maxV = INT_MIN;
        int count;
        for (auto i : nums) {
            if (i > maxV) {
                maxV = i;
            }
            if (i < minV) {
                minV = i;
            }
        }

        for (auto i : nums) {
            if (i > minV && i < maxV) {
                count++;
            }
        }
        return count;
    }
};