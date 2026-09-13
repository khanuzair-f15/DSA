class Solution {
public:
    vector<int> intersection(vector<int>& nums1, vector<int>& nums2) {
        vector<int> ans;
        unordered_set<int> s;

        for (int i = 0; i < nums1.size(); i++) {
            s.insert(nums1[i]);
        }

        for (int i = 0; i < nums2.size(); i++) {
            if (s.count(nums2[i])) {
                ans.push_back(nums2[i]);
                s.erase(nums2[i]);
            }
        }

        return ans;
        // using stl set intersection
        /*
        set<int> result; // used to store the common element
        // sort the vector so i can do the set intersection
        sort(nums1.begin(), nums1.end());
        sort(nums2.begin(), nums2.end());

        set_intersection(nums1.begin(), nums1.end(), // first sortered vector
                         nums2.begin(), nums2.end(), // second sortered vector
                         inserter(result, result.begin())); //

        vector<int> ans(result.begin(), result.end());
        return ans;
        */
    }
};