// Untested draft copied verbatim from docs/VEGAS_NOTES.md Section 10. Do not run on real projects.
using System;
using System.IO;
using System.Text;
using System.Windows.Forms;
using ScriptPortal.Vegas;   // change to Sony.Vegas only if VQ-01 shows it is required

public class EntryPoint
{
    StringBuilder sb = new StringBuilder();

    static string Esc(string s)
    {
        if (s == null) return "";
        return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", " ").Replace("\n", " ");
    }

    void Walk(PlugInNode node, string category, int depth)
    {
        // Containers (folders) may hold children. Leaves are real plugins.
        // IsContainer / enumeration behavior is unverified; adjust if it throws.
        bool container = false;
        try { container = node.IsContainer; } catch { }

        if (container)
        {
            foreach (PlugInNode child in node)
            {
                Walk(child, category, depth + 1);
            }
        }
        else
        {
            sb.Append("    {\"category\":\"").Append(category).Append("\",");
            sb.Append("\"name\":\"").Append(Esc(node.Name)).Append("\",");
            sb.Append("\"unique_id\":\"").Append(Esc(node.UniqueID)).Append("\",");
            sb.Append("\"is_ofx\":").Append(node.IsOFX ? "true" : "false").Append(",");
            sb.Append("\"depth\":").Append(depth).Append("},\r\n");
        }
    }

    public void FromVegas(Vegas vegas)
    {
        try
        {
            string dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "VegasAgent\\probes");
            Directory.CreateDirectory(dir);

            sb.Append("{\r\n  \"plugins\": [\r\n");
            foreach (PlugInNode n in vegas.Transitions) Walk(n, "transition", 0);
            foreach (PlugInNode n in vegas.VideoFX)     Walk(n, "video_fx", 0);
            foreach (PlugInNode n in vegas.AudioFX)     Walk(n, "audio_fx", 0);
            foreach (PlugInNode n in vegas.Generators)  Walk(n, "generator", 0);
            sb.Append("    {}\r\n  ]\r\n}\r\n");   // trailing {} keeps the JSON valid after trailing commas

            string path = Path.Combine(dir, "catalog_dump.json");
            File.WriteAllText(path, sb.ToString(), Encoding.UTF8);
            MessageBox.Show("Wrote " + path);
        }
        catch (Exception e)
        {
            MessageBox.Show("CatalogDump failed: " + e.ToString());
        }
    }
}
