class Solution {
public:
    int getCommon(vector<int>& nums1, vector<int>& nums2) {

        int ans = INT_MAX, i = 0, j = 0, flag = 0;

        // 1 2 3
        // 2 4
        while (i < nums1.size() && j < nums2.size()) {
            if (nums1[i] == nums2[j]) {
                ans = min(nums1[i], ans);
                flag++;
                i++;
                j++;
            } else if (nums1[i] < nums2[j]) {
                i++;
            } else {
                j++;
            }
        }
        if (flag == 0) {
            return -1;
        }
        return ans;
    }
};